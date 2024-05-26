# local_instance.py
import subprocess, os
from time import sleep

instance = None
port = 11435

def start(data_dir):
    instance = subprocess.Popen(["/app/bin/ollama", "serve"], env={**os.environ, 'OLLAMA_HOST': f"127.0.0.1:{port}", "HOME": data_dir}, stderr=subprocess.PIPE, text=True)
    print("Starting Alpaca's Ollama instance...")
    sleep(1)
    while True:
        err = instance.stderr.readline()
        if err == '' and instance.poll() is not None:
            break
        if 'msg="inference compute"' in err: #Ollama outputs a line with this when it finishes loading, yeah
            break
    print("Started Alpaca's Ollama instance")

def stop():
    if instance: instance.kill()
    print("Stopped Alpaca's Ollama instance")

