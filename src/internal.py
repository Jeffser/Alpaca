import os

app_id = "com.jeffser.Alpaca"

in_flatpak = True if os.getenv("FLATPAK_ID") else False

def get_xdg_home(env, default):
    if in_flatpak:
        return os.getenv(env)
    else:
        base = os.getenv(env) or os.path.expanduser(default)
        path = os.path.join(base, app_id)
        if not os.path.exists(path):
            os.makedirs(path)
        return path


data_dir = get_xdg_home("XDG_DATA_HOME", "~/.local/share")
config_dir = get_xdg_home("XDG_CONFIG_HOME", "~/.config")
cache_dir = get_xdg_home("XDG_CACHE_HOME", "~/.cache")

source_dir = os.path.abspath(os.path.dirname(__file__))
