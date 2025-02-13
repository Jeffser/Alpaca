# instance_manager.py
"""
Manages AI instances (Ollama, OpenAI)
"""

import openai
import requests

class instance:

    def __init__(self, instance_url:str='http://0.0.0.0:11434', instance_key:str='', api_type:str='ollama'):
        self.instance_url = instance_url
        self.instance_key = instance_key
        self.api_type = api_type

    def request(self, connection_type:str, connection_url:str, data:dict=None, callback:callable=None) -> requests.models.Response:
        headers = self.get_headers()
        response = None
        if connection_type == "GET":
            response = requests.get(connection_url, headers=headers)
        elif connection_type == "POST":
            if callback:
                response = requests.post(connection_url, headers=headers, data=data, stream=True)
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            callback(json.loads(line.decode("utf-8")))
            else:
                response = requests.post(connection_url, headers=headers, data=data, stream=False)
        elif connection_type == "DELETE":
            response = requests.delete(connection_url, headers=headers, data=data)
        return response

    def get_headers(self) -> dict:
        headers = {}
        if self.api_type == 'openai':
            headers["Authorization"] = f"Bearer {self.instance_key}"
            headers["Content-Type"] = "application/json"
        return headers
