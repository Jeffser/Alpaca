# connectionhandler.py
import json, requests

url = None
bearer_token = None

def get_headers(include_json:bool) -> dict:
    headers = {}
    if include_json:
        headers["Content-Type"] = "application/json"
    if bearer_token:
        headers["Authorization"] = "Bearer {}".format(bearer_token)
    return headers if len(headers.keys()) > 0 else None

def simple_get(connection_url:str) -> dict:
    try:
        response = requests.get(connection_url, headers=get_headers(False))
        if response.status_code == 200:
            return {"status": "ok", "text": response.text, "status_code": response.status_code}
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}

def simple_post(connection_url:str, data) -> dict:
    try:
        response = requests.post(connection_url, headers=get_headers(True), data=data, stream=False)
        if response.status_code == 200:
            return {"status": "ok", "text": response.text, "status_code": response.status_code}
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}

def simple_delete(connection_url:str, data) -> dict:
    try:
        response = requests.delete(connection_url, headers=get_headers(False), json=data)
        if response.status_code == 200:
            return {"status": "ok", "status_code": response.status_code}
        else:
            return {"status": "error", "text": "Failed to delete", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}

def stream_post(connection_url:str, data, callback:callable) -> dict:
    try:
        response = requests.post(connection_url, headers=get_headers(True), data=data, stream=True)
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    callback(json.loads(line.decode("utf-8")))
            return {"status": "ok", "status_code": response.status_code}
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "status_code": 0}
