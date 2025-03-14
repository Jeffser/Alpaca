# generation_tools.py

import logging, json
logger = logging.getLogger(__name__)

import datetime, time, random, threading

action_list = [{
    "metadata": {
        "name": "Get Datetime",
        "description": "Gets the current date and time in the specified strftime format",
        "author": "Jeffser"
    },
    "parameters": [
        {
            "name": "format",
            "type": "string",
            "description": "The strftime format to use when retrieving the current date and time",
            "required": True,
            "show": True
        }
    ]
    "variables": [
        {
            "name": "Current Time",
            "default": "",
            "show": True
        },
        {
            "name": "Message",
            "default": "",
            "show": False
        }
    ],
    "functions": [
        {
            "name": "Get Current Time",
            "parameters": [
                {
                    "name": "format",
                    "method": "parameter",
                    "value": "format"
                }
            ],
            "return": "Current Time"
        },
        {
            "name": "Concatenate Text",
            "parameters": [
                {
                    "name": "texts",
                    "method": "list",
                    "value": [
                        {
                            "method": "constant",
                            "value": "The time is "
                        },
                        {
                            "method": "variable",
                            "value": "Current Time"
                        }
                    ]
                }
            ],
            "return": "Message"
        },
        {
            "name": "Show Message",
            "parameters": [
                {
                    "name": "animate",
                    "method": "constant",
                    "value": True
                },
                {
                    "name": "text",
                    "method": "variable",
                    "value": "Message"
                }
            ]
        }
    ]
}]

class get_current_time:
    """
    Gets the current time in the specified format
    Parameters:
        - format
          - type: str
          - default: %I:%M:%S %p
    Returns current time in format (str)
    """


    def run(self, **args):
        time_format = args.get('format', '%I:%M:%S %p')
        return datetime.datetime.now().strftime(time_format)

class concatenate_text:
    """
    Concatenates one or more strings
    Parameters:
        - texts
            - type: list
    Returns concatenated text (str)
    """

    def run(self, **args):
        text ''.join([str(t) for t in args.get('texts', [])])
        return text

class action:
    messages = []
    runtime_env = {}
    functions = []

    def __init__(self, messages:list, action_name:str, parameters:dict):
        found_actions = [a for a in action_list if a.get('metadata', {}).get('name') == action_name]
        if len(found_actions) == 0:
            return {'error': _('Action not found)}
        self.action = found_actions[0]
        self.messages = messages
        self.runtime_env['variables'] = {v.get('name'): v.get('default') for v in action.get('variables')}
        self.runtime_env['parameters'] = parameters
        calls = {
            "Get Current Time": get_current_time,
            "Concatenate Text": concatenate_text,
            "Show Message": self.show_message
        }
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
            response = f.get('call').run(**params)
            if f.get('return'):
                self.runtime_env.get('variables')[f.get('return')] = response
        return "# {}\n{}\n{}"

    def show_message(self, **args) -> None:
        """
        Outputs text to the message element
        Parameters:
            - text
                - type: str
            - animate (Add small delay to every word, simulating text generation)
                - type: bool
                - default: True
        """
        animate = args.get('animate', True)
        if args.get("text"):
            for word in args.get('text').split(' '):
                #self.messages[-1].update_message({"content": '{} '.format(word)})
                if animate:
                    time.sleep(round(random.uniform(0.01, 1.00), 3))

