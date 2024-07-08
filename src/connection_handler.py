# connection_handler.py
import json, requests
#OK=200 response.status_code
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
    return requests.get(connection_url, headers=get_headers(False))

def simple_post(connection_url:str, data) -> dict:
    return requests.post(connection_url, headers=get_headers(True), data=data, stream=False)

def simple_delete(connection_url:str, data) -> dict:
    return requests.delete(connection_url, headers=get_headers(False), json=data)

def stream_post(connection_url:str, data, callback:callable) -> dict:
    response = requests.post(connection_url, headers=get_headers(True), data=data, stream=True)
    if response.status_code == 200:
        for line in response.iter_lines():
            if line:
                callback(json.loads(line.decode("utf-8")))
    return response
