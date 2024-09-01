# connection_handler.py
"""
Handles requests to remote and integrated instances of Ollama
"""
import json, os, requests, subprocess, threading
from .internal import data_dir, cache_dir
from logging import getLogger
from time import sleep

logger = getLogger(__name__)

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

    def __init__(self, local_port:int, remote_url:str, remote:bool, tweaks:dict, overrides:dict, bearer_token:str):
        self.local_port=local_port
        self.remote_url=remote_url
        self.remote=remote
        self.tweaks=tweaks
        self.overrides=overrides
        self.bearer_token=bearer_token
        self.instance = None
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
        connection_url = '{}/{}'.format(self.remote_url if self.remote else 'http://127.0.0.1:{}'.format(self.local_port), connection_url)
        logger.info('Connection: {} : {}'.format(connection_type, connection_url))
        match connection_type:
            case "GET":
                return requests.get(connection_url, headers=self.get_headers(False))
            case "POST":
                if callback:
                    response = requests.post(connection_url, headers=self.get_headers(True), data=data, stream=True)
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if line:
                                callback(json.loads(line.decode("utf-8")))
                    return response
                else:
                    return requests.post(connection_url, headers=self.get_headers(True), data=data, stream=False)
            case "DELETE":
                return requests.delete(connection_url, headers=self.get_headers(False), json=data)

    def start(self):
        if not os.path.isdir(os.path.join(cache_dir, 'tmp/ollama')):
            os.mkdir(os.path.join(cache_dir, 'tmp/ollama'))

        params = self.overrides.copy()
        params["OLLAMA_DEBUG"] = "1"
        params["OLLAMA_HOST"] = f"127.0.0.1:{self.local_port}" # You can't change this directly sorry :3
        params["HOME"] = data_dir
        params["TMPDIR"] = os.path.join(cache_dir, 'tmp/ollama')
        self.instance = subprocess.Popen(["ollama", "serve"], env={**os.environ, **params}, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        threading.Thread(target=log_output, args=(self.instance.stdout,)).start()
        threading.Thread(target=log_output, args=(self.instance.stderr,)).start()
        logger.info("Starting Alpaca's Ollama instance...")
        logger.debug(params)
        logger.info("Started Alpaca's Ollama instance")
        v_str = subprocess.check_output("ollama -v", shell=True).decode('utf-8')
        logger.info('Ollama version: {}'.format(v_str.split('client version is ')[1].strip()))

    def stop(self):
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
