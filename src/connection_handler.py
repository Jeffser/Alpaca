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

AMD_support_label = "\n<a href='https://github.com/Jeffser/Alpaca/wiki/AMD-Support'>{}</a>".format(_('Alpaca Support'))

def log_output(pipe):
    with open(os.path.join(data_dir, 'tmp.log'), 'a') as f:
        with pipe:
            try:
                for line in iter(pipe.readline, ''):
                    #print(line, end='')
                    f.write(line)
                    f.flush()
                    if 'msg="model request too large for system"' in line:
                        window.show_toast(_("Model request too large for system"), window.main_overlay)
                    elif 'msg="amdgpu detected, but no compatible rocm library found.' in line:
                        if bool(os.getenv("FLATPAK_ID")):
                            window.ollama_information_label.set_label(_("AMD GPU detected but the extension is missing, Ollama will use CPU.") + AMD_support_label)
                        else:
                            window.ollama_information_label.set_label(_("AMD GPU detected but ROCm is missing, Ollama will use CPU.") + AMD_support_label)
                        window.ollama_information_label.set_css_classes(['dim-label', 'error'])
                    elif 'msg="amdgpu is supported"' in line:
                        window.ollama_information_label.set_label(_("Using AMD GPU type '{}'").format(line.split('=')[-1].replace('\n', '')))
                        window.ollama_information_label.set_css_classes(['dim-label', 'success'])
            except Exception as e:
                pass

class instance():

    def __init__(self):
        preferences = window.sql_instance.get_preferences()
        self.local_port = preferences.get('local_port', 11435)
        self.remote_url = preferences.get('remote_url', 'http://0.0.0.0:11434')
        self.remote = preferences.get('run_remote', False)
        self.tweaks = {
            'temperature': preferences.get('temperature', 0.7),
            'seed': preferences.get('seed', 0),
            'keep_alive': preferences.get('keep_alive', 5)
        }
        self.overrides = window.sql_instance.get_overrides()
        self.bearer_token = preferences.get('remote_bearer_token', "")
        self.model_directory = preferences.get('model_directory', os.path.join(data_dir, '.ollama', 'models'))
        self.idle_timer_delay = preferences.get('idle_timer', 0)
        self.idle_timer_stop_event = threading.Event()
        self.idle_timer = None
        self.instance = None
        self.busy = 0

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
        if self.remote:
            logger.info('{} : {}'.format(connection_type, connection_url))
        response = None
        if connection_type == "GET":
            response = requests.get(connection_url, headers=self.get_headers(False))
        elif connection_type == "POST":
            if callback:
                response = requests.post(connection_url, headers=self.get_headers(True), data=data, stream=True)
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            callback(json.loads(line.decode("utf-8")))
            else:
                response = requests.post(connection_url, headers=self.get_headers(True), data=data, stream=False)
        elif connection_type == "DELETE":
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
        self.stop()
        if shutil.which('ollama'):
            if not os.path.isdir(os.path.join(cache_dir, 'tmp/ollama')):
                os.mkdir(os.path.join(cache_dir, 'tmp/ollama'))
            self.instance = None
            params = self.overrides.copy()
            params["OLLAMA_HOST"] = f"127.0.0.1:{self.local_port}" # You can't change this directly sorry :3
            params["OLLAMA_MODELS"] = self.model_directory
            params["TMPDIR"] = os.path.join(cache_dir, 'tmp/ollama')
            instance = subprocess.Popen(["ollama", "serve"], env={**os.environ, **params}, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            threading.Thread(target=log_output, args=(instance.stdout,)).start()
            threading.Thread(target=log_output, args=(instance.stderr,)).start()
            logger.info("Starting Alpaca's Ollama instance...")
            logger.debug(params)
            logger.info("Started Alpaca's Ollama instance")
            try:
                v_str = subprocess.check_output("ollama -v", shell=True).decode('utf-8')
                logger.info(v_str.split('\n')[1].strip('Warning: ').strip())
            except Exception as e:
                logger.error(e)
            self.instance = instance
            if not self.idle_timer:
                self.start_timer()
            window.ollama_information_label.set_label(_("Integrated Ollama instance is running"))
            window.ollama_information_label.set_css_classes(['dim-label', 'success'])
        else:
            self.remote = True
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
            window.ollama_information_label.set_label(_("Integrated Ollama instance is not running"))
            window.ollama_information_label.set_css_classes(['dim-label'])
            logger.info("Stopped Alpaca's Ollama instance")

    def reset(self):
        logger.info("Resetting Alpaca's Ollama instance")
        self.stop()
        sleep(1)
        self.start()
