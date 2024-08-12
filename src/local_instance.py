# local_instance.py
"""
Handles running, stopping and resetting the integrated Ollama instance
"""
import subprocess
import threading
import os
from time import sleep
from logging import getLogger
from .internal import data_dir, cache_dir


logger = getLogger(__name__)

instance = None
port = 11435
overrides = {}

def log_output(pipe):
    with open(os.path.join(data_dir, 'tmp.log'), 'a') as f:
        with pipe:
            for line in iter(pipe.readline, ''):
                print(line, end='')
                f.write(line)
                f.flush()

def start():
    if not os.path.isdir(os.path.join(cache_dir, 'tmp/ollama')):
        os.mkdir(os.path.join(cache_dir, 'tmp/ollama'))
    global instance
    params = overrides.copy()
    params["OLLAMA_HOST"] = f"127.0.0.1:{port}" # You can't change this directly sorry :3
    params["HOME"] = data_dir
    params["TMPDIR"] = os.path.join(cache_dir, 'tmp/ollama')
    instance = subprocess.Popen(["ollama", "serve"], env={**os.environ, **params}, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    threading.Thread(target=log_output, args=(instance.stdout,)).start()
    threading.Thread(target=log_output, args=(instance.stderr,)).start()
    logger.info("Starting Alpaca's Ollama instance...")
    logger.debug(params)
    sleep(1)
    logger.info("Started Alpaca's Ollama instance")
    v_str = subprocess.check_output("ollama -v", shell=True).decode('utf-8')
    logger.info('Ollama version: {}'.format(v_str.split('client version is ')[1].strip()))

def stop():
    logger.info("Stopping Alpaca's Ollama instance")
    global instance
    if instance:
        instance.terminate()
        instance.wait()
        instance = None
        logger.info("Stopped Alpaca's Ollama instance")

def reset():
    logger.info("Resetting Alpaca's Ollama instance")
    stop()
    sleep(1)
    start()
