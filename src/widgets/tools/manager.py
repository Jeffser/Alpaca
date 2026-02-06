# manager.py

from gi.repository import Gtk, Gio, Adw, Gdk, GLib
from .tools import Base
from .selector import tool_selector_model
import importlib.util

class MCPServer(Adw.ExpanderRow):
    __gtype_name__ = 'AlpacaMCPServer'

    def __init__(self, name:str, tool_list:list, pinned:bool=False):
        super().__init__(
            title=name
        )
        global tool_selector_model

        self.tools_count = len(tool_list)

        if not pinned:
            remove_button = Gtk.Button(
                valign=3,
                icon_name='user-trash-symbolic',
                tooltip_text=_("Remove MCP Server"),
                css_classes=["flat", "error"]
            )
            self.add_prefix(remove_button)

        if len(tool_list) == 0:
            warning_icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic')
            warning_icon.add_css_class('warning')
            warning_icon.set_tooltip_text(_("No Tools Found"))
            warning_icon.set_valign(3)
            self.add_prefix(warning_icon)

        for i, tool in enumerate(tool_list):
            if tool.runnable:
                row = Adw.SwitchRow(
                    title=tool.display_name,
                    subtitle=tool.description,
                    icon_name=tool.icon_name
                )
                self.add_row(row)
                row.connect('notify::active', lambda sr, ud, t=tool, index=i: self.tool_state_changed(sr, t, index))
                if tool.enabled_by_default:
                    GLib.idle_add(row.set_active, True)
            else:
                tool_selector_model.append(tool)

    def tool_state_changed(self, switch_row, tool, index):
        mcp_servers_list = list(self.get_ancestor(ToolManager).list_box)
        mcp_servers_list = mcp_servers_list[:mcp_servers_list.index(self)]
        tool_count = sum([row.tools_count for row in mcp_servers_list])

        if switch_row.get_active():
            tool_selector_model.insert(tool_count+index, tool)
        else:
            tool_selector_model.remove(tool_count+index)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/tools/manager.ui')
class ToolManager(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaToolManager'

    list_box = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

        base_tools = []
        for tool in Base.__subclasses__():
            if all(importlib.util.find_spec(lib) for lib in tool.required_libraries) or len(tool.required_libraries) == 0:
                base_tools.append(tool())

        self.list_box.append(
            MCPServer(
                "Alpaca MCP",
                base_tools,
                pinned=True
            )
        )

    @Gtk.Template.Callback()
    def add_mcp_server(self, button):
        print(button)
