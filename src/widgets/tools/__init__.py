from ...sql_manager import Instance as SQL

import time, random

from .tools import Base
from .notebook_tools import tools as NotebookTools

def log_to_message(text:str, bot_message, animate:bool):
    for s in text.split(' '):
        bot_message.update_message({"content": '{} '.format(s)})
        if animate:
            time.sleep(round(random.random()/4, 2))
    bot_message.update_message({"content": "\n"})

def update_available_tools(listbox):
    tools_parameters = SQL.get_tool_parameters()
    for ac in Base.__subclasses__():
        tool_parameters = tools_parameters.get(ac.tool_metadata.get('name'), {})
        tool_element = ac(tool_parameters.get('variables', {}), tool_parameters.get('activated', False))
        listbox.prepend(tool_element)

def get_enabled_tools(listbox) -> dict:
    tools = {}
    for t in list(listbox):
        if t.is_enabled():
            tools[t.tool_metadata.get('name')] = t
    return tools

def get_tool(tool_name:str, listbox):
    tools = [a for a in list(listbox) if a.tool_metadata.get('name') == tool_name]
    if tools:
        return tools[0]

def run_tool(tool_name:str, arguments:dict, messages:list, bot_message, listbox):
    tool = get_tool(tool_name, listbox)
    if tool:
        response = tool.run(arguments, messages, bot_message)
        return response
