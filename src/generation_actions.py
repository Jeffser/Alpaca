# generation_actions.py

import logging, json, os
logger = logging.getLogger(__name__)

import datetime, time, random, threading

window = None

class test_message: # To test append_message
    def update_message(data:dict):
        print(data.get('content'), end='')

class get_current_time:
    """
    Parameters:
        - format
          - type: str
          - default: %I:%M:%S %p
    Returns current time in format (str)
    """
    name="Get Current Time"
    description="Gets the current time in the specified format"

    def run(**args):
        time_format = args.get('format', '%I:%M:%S %p')
        return datetime.datetime.now().strftime(time_format)

class concatenate_text:
    """
    Parameters:
        - texts
            - type: list
    Returns concatenated text (str)
    """
    name="Concatenate Text"
    description="Concatenates one or more strings"

    def run(**args):
        texts = args.get('texts', [])
        text = ''.join([str(t) for t in texts])
        return text

class append_message:
    """
    Parameters:
        - text
            - type: str
        - animate (Add small delay to every word, simulating text generation)
            - type: bool
            - default: True
        - message (Auto added when deployed)
            - type: dynamic
    """
    name="Show Message"
    description="Appends text to bot message using Alpaca's message update system"

    def run(**args) -> None:
        animate = args.get('animate', True)
        text = args.get('text', None)
        message = args.get('message', None)
        if text and message:
            for word in args.get('text').split(' '):
                message.update_message({"content": '{} '.format(word)})
                if animate:
                    time.sleep(round(random.uniform(0.01, 1.00), 3))

available_calls=[get_current_time, concatenate_text, append_message]

class Action:
    messages = []
    runtime_env = {}
    functions = []

    def __init__(self, messages:list, action:dict, parameters:dict):
        self.action = action
        self.messages = messages
        self.runtime_env['variables'] = {v.get('name'): v.get('default') for v in action.get('variables')}
        self.runtime_env['parameters'] = parameters
        calls = {c.name: c for c in available_calls}
        for f in self.action.get('functions'):
            f['call'] = calls.get(f.get('name'), lambda: None)
            self.functions.append(f)

    def get_value(self, method:str, value):
        if method == 'constant':
            return value
        if method == 'variable':
            return self.runtime_env.get('variables').get(value)
        if method == 'parameter':
            return self.runtime_env.get('parameters').get(value)
        if method == 'list':
            result_list = []
            for l in value:
                result_list.append(self.get_value(l.get('method'), l.get('value')))
            return result_list

    def run(self):
        for f in self.functions:
            params = {}
            for p in f.get('parameters', []):
                params[p.get('name')] = self.get_value(p.get('method'), p.get('value'))
            response = f.get('call').run(**params, message=self.messages[-1])
            if f.get('return'):
                self.runtime_env.get('variables')[f.get('return')] = response

class Manager:
    loaded_actions = {}

    def __init__(self, integrated_actions_path:str):
        with open(integrated_actions_path, 'r', encoding='utf-8') as f:
            for action_id, action in json.load(f).items():
                function_name = action.get('metadata').get('name').replace(' ', '_').lower()
                self.loaded_actions[function_name] = {
                    'tool': self.get_tool(action, function_name),
                    'action': action,
                    'enabled': True,
                    'id': action_id
                }

    def run(self, function_name:str, params:dict):
        action = self.loaded_actions.get(function_name, {}).get('action')
        if action:
            action_runner = Action([test_message], action, params)
            action_runner.run()

    def get_available_tools(self) -> list:
        tools = []
        for name, action in loaded_actions.items():
            if action.get('enabled'):
                tools.append(action.get('tool'))
        return tools

    def get_tool(self, action:dict, name:str) -> dict: # Converts action to tool for AIs to understand
        description = action.get('metadata', {}).get('description')
        if name and description:
            parameters = {}
            required_parameters = []
            for p in action.get('parameters'):
                if p.get('name') and p.get('type') and p.get('description'):
                    parameters[p.get('name')] = {}
                    parameters.get(p.get('name'))['type'] = p.get('type')
                    parameters.get(p.get('name'))['description'] = p.get('description')
                    if p.get('required', False):
                        required_parameters.append(p.get('name'))
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required_parameters,
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }

