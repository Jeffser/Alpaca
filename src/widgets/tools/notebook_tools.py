# notebook_tools.py

from gi.repository import GLib

class Base:
    def get_tool(self) -> dict:
        return {
            "type": "function",
            "function": self.tool_metadata
        }

class ReadNotebook(Base):
    tool_metadata = {
        "name": "read_notebook",
        "description": "Gets the current content of the notebook.",
        "parameters": {}
    }
    name = _("Read Notebook")
    description = _("Reads the current notebook.")

    def run(self, arguments, bot_message) -> str:
        return bot_message.chat.get_notebook()

class WriteNotebook(Base):
    tool_metadata = {
        "name": "write_notebook",
        "description": "Overwrite the entire notebook with new content.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full new content of the notebook"
                }
            }
        }
    }
    name = _("Write Notebook")
    description = _("Overwrites the notebook with new text.")

    def run(self, arguments, bot_message) -> str:
        GLib.idle_add(bot_message.chat.set_notebook, arguments.get('content'))

class AppendToNotebook(Base):
    tool_metadata = {
        "name": "append_to_notebook",
        "description": "Append text to the notebook.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text to append"
                }
            }
        }
    }
    name = _("Append to Notebook")
    description = _("Appends text to the notebook.")

    def run(self, arguments, bot_message) -> str:
        GLib.idle_add(bot_message.chat.append_notebook, arguments.get('content'))


tools = {}

for t in (ReadNotebook, WriteNotebook, AppendToNotebook):
    tools[t.tool_metadata.get('name')] = t()
