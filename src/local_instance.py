# local_instance.py
import subprocess, os, threading
from time import sleep
from logging import getLogger


logger = getLogger(__name__)

instance = None
port = 11435
data_dir = os.getenv("XDG_DATA_HOME")
overrides = {}

def start():
    global instance, overrides
    params = overrides.copy()
    params["OLLAMA_HOST"] = f"127.0.0.1:{port}" # You can't change this directly sorry :3
    params["HOME"] = data_dir
    instance = subprocess.Popen(["/app/bin/ollama", "serve"], env={**os.environ, **params}, stderr=subprocess.PIPE, text=True)
    logger.info("Starting Alpaca's Ollama instance...")
    sleep(1)
    logger.info("Started Alpaca's Ollama instance")

def stop():
    global instance
    if instance:
        instance.terminate()
        instance.wait()
        instance = None
        logger.info("Stopped Alpaca's Ollama instance")

def reset():
    stop()
    sleep(1)
    start()

