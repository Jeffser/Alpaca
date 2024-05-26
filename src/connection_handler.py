# connectionhandler.py
import json, requests

url = None

def simple_get(connection_url:str) -> dict:
    try:
        response = requests.get(connection_url)
        if response.status_code == 200:
            return {"status": "ok", "text": response.text, "status_code": response.status_code}
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}

def simple_delete(connection_url:str, data) -> dict:
    try:
        response = requests.delete(connection_url, json=data)
        if response.status_code == 200:
            return {"status": "ok", "status_code": response.status_code}
        else:
            return {"status": "error", "text": "Failed to delete", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}

def stream_post(connection_url:str, data, callback:callable) -> dict:
    try:
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(connection_url, headers=headers, data=data, stream=True)
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    callback(json.loads(line.decode("utf-8")))
            return {"status": "ok", "status_code": response.status_code}
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}

