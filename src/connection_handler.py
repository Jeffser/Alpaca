# connection_handler.py
"""
Handles requests to remote and integrated instances of Ollama
"""
import json, os, requests, subprocess, threading, shutil
from .internal import data_dir, cache_dir
from logging import getLogger
from time import sleep

logger = getLogger(__name__)

window = None

def log_output(pipe):
    with open(os.path.join(data_dir, 'tmp.log'), 'a') as f:
        with pipe:
            try:
                for line in iter(pipe.readline, ''):
                    print(line, end='')
                    f.write(line)
                    f.flush()
            except:
                pass

class instance():

    def __init__(self, local_port:int, remote_url:str, remote:bool, tweaks:dict, overrides:dict, bearer_token:str, idle_timer_delay:int):
        self.local_port=local_port
        self.remote_url=remote_url
        self.remote=remote
        self.tweaks=tweaks
        self.overrides=overrides
        self.bearer_token=bearer_token
        self.idle_timer_delay=idle_timer_delay
        self.idle_timer_stop_event=threading.Event()
        self.idle_timer=None
        self.instance=None
        self.busy=0
        if not self.remote:
            self.start()

    def get_headers(self, include_json:bool) -> dict:
        headers = {}
        if include_json:
            headers["Content-Type"] = "application/json"
        if self.bearer_token and self.remote:
            headers["Authorization"] = "Bearer " + self.bearer_token
        return headers if len(headers.keys()) > 0 else None

    def request(self, connection_type:str, connection_url:str, data:dict=None, callback:callable=None) -> requests.models.Response:
        self.busy += 1
        if self.idle_timer and not self.remote:
            self.idle_timer_stop_event.set()
            self.idle_timer=None
        if not self.instance and not self.remote:
            self.start()
        connection_url = '{}/{}'.format(self.remote_url if self.remote else 'http://127.0.0.1:{}'.format(self.local_port), connection_url)
        logger.info('{} : {}'.format(connection_type, connection_url))
        response = None
        match connection_type:
            case "GET":
                response = requests.get(connection_url, headers=self.get_headers(False))
            case "POST":
                if callback:
                    response = requests.post(connection_url, headers=self.get_headers(True), data=data, stream=True)
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if line:
                                callback(json.loads(line.decode("utf-8")))
                else:
                    response = requests.post(connection_url, headers=self.get_headers(True), data=data, stream=False)
            case "DELETE":
                response = requests.delete(connection_url, headers=self.get_headers(False), data=data)
        self.busy -= 1
        if not self.idle_timer and not self.remote:
            self.start_timer()
        return response

    def run_timer(self):
        if not self.idle_timer_stop_event.wait(self.idle_timer_delay*60):
            window.show_toast(_("Ollama instance was shut down due to inactivity"), window.main_overlay)
            self.stop()

    def start_timer(self):
        if self.busy == 0:
            if self.idle_timer:
                self.idle_timer_stop_event.set()
                self.idle_timer=None
            if self.idle_timer_delay > 0 and self.busy == 0:
                self.idle_timer_stop_event.clear()
                self.idle_timer = threading.Thread(target=self.run_timer)
                self.idle_timer.start()

    def start(self):
        if shutil.which('ollama'):
            if not os.path.isdir(os.path.join(cache_dir, 'tmp/ollama')):
                os.mkdir(os.path.join(cache_dir, 'tmp/ollama'))
            self.instance = None
            params = self.overrides.copy()
            params["OLLAMA_DEBUG"] = "1"
            params["OLLAMA_HOST"] = f"127.0.0.1:{self.local_port}" # You can't change this directly sorry :3
            params["HOME"] = data_dir
            params["TMPDIR"] = os.path.join(cache_dir, 'tmp/ollama')
            instance = subprocess.Popen(["ollama", "serve"], env={**os.environ, **params}, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            threading.Thread(target=log_output, args=(instance.stdout,)).start()
            threading.Thread(target=log_output, args=(instance.stderr,)).start()
            logger.info("Starting Alpaca's Ollama instance...")
            logger.debug(params)
            logger.info("Started Alpaca's Ollama instance")
            v_str = subprocess.check_output("ollama -v", shell=True).decode('utf-8')
            logger.info('Ollama version: {}'.format(v_str.split('client version is ')[1].strip()))
            self.instance = instance
            if not self.idle_timer:
                self.start_timer()
        else:
            self.remote = True
            if not self.remote_url:
                window.remote_connection_entry.set_text('http://0.0.0.0:11434')
            window.remote_connection_switch.set_sensitive(True)
            window.remote_connection_switch.set_active(True)

    def stop(self):
        if self.idle_timer:
            self.idle_timer_stop_event.set()
            self.idle_timer=None
        if self.instance:
            logger.info("Stopping Alpaca's Ollama instance")
            self.instance.terminate()
            self.instance.wait()
            self.instance = None
            logger.info("Stopped Alpaca's Ollama instance")

    def reset(self):
        logger.info("Resetting Alpaca's Ollama instance")
        self.stop()
        sleep(1)
        self.start()
