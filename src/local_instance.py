# local_instance.py
import subprocess, os, threading
from time import sleep

instance = None
port = 11435
data_dir = os.getenv("XDG_DATA_HOME")

def start():
    global instance
    instance = subprocess.Popen(["/app/bin/ollama", "serve"], env={**os.environ, 'OLLAMA_HOST': f"127.0.0.1:{port}", "HOME": data_dir}, stderr=subprocess.PIPE, text=True)
    print("Starting Alpaca's Ollama instance...")
    sleep(1)
    print("Started Alpaca's Ollama instance")

def stop():
    global instance
    if instance:
        instance.kill()
        instance.wait()
        instance = None
        print("Stopped Alpaca's Ollama instance")

def reset():
    stop()
    sleep(1)
    start()

