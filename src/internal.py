# internal.py
"""
Handles paths, they can be different if the app is running as a Flatpak
"""

import os

from .constants import APP_ID


# The identifier when inside the Flatpak runtime
IN_FLATPAK = bool(os.getenv("FLATPAK_ID"))

def get_xdg_home(env, default):
    if IN_FLATPAK:
        return os.getenv(env)
    base = os.getenv(env) or os.path.expanduser(default)
    path = os.path.join(base, APP_ID)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


data_dir = get_xdg_home("XDG_DATA_HOME", "~/.local/share")
config_dir = get_xdg_home("XDG_CONFIG_HOME", "~/.config")
cache_dir = get_xdg_home("XDG_CACHE_HOME", "~/.cache")

source_dir = os.path.abspath(os.path.dirname(__file__))
