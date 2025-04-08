# constants.py
"""
Holds a few constant values that can be re-used all over the application.
"""
import os


# The app identifier
APP_ID = "com.jeffser.Alpaca"


# Big thanks to everyone contributing translations.
# These translators will be shown inside of the app under
# "About Alpaca" > "Contributors".
TRANSLATORS: "list[str]" = [
    "Alex K (Russian) https://github.com/alexkdeveloper",
    "DasHi (Russian) https://github.com/col83",
    "Jeffry Samuel (Spanish) https://github.com/jeffser",
    "Louis Chauvet-Villaret (French) https://github.com/loulou64490",
    "Théo FORTIN (French) https://github.com/topiga",
    "Daimar Stein (Brazilian Portuguese) https://github.com/not-a-dev-stein",
    "Bruno Antunes (Brazilian Portuguese) https://github.com/antun3s",
    "CounterFlow64 (Norwegian) https://github.com/CounterFlow64",
    "Aritra Saha (Bengali) https://github.com/olumolu",
    "Yuehao Sui (Simplified Chinese) https://github.com/8ar10der",
    "Aleksana (Simplified Chinese) https://github.com/Aleksanaa",
    "Aritra Saha (Hindi) https://github.com/olumolu",
    "YusaBecerikli (Turkish) https://github.com/YusaBecerikli",
    "Simon (Ukrainian) https://github.com/OriginalSimon",
    "Marcel Margenberg (German) https://github.com/MehrzweckMandala",
    "Magnus Schlinsog (German) https://github.com/mags0ft",
    "Edoardo Brogiolo (Italian) https://github.com/edo0",
    "Shidore (Japanese) https://github.com/sh1d0re",
    "Henk Leerssen (Dutch) https://github.com/Henkster72",
    "Nofal Briansah (Indonesian) https://github.com/nofalbriansah",
    "Harimanish (Tamil) https://github.com/harimanish",
    "Ekaterine Papava (Georgian) https://github.com/EkaterinePapava"
]

# Used to populate SR language in preferences
SPEACH_RECOGNITION_LANGUAGES = ('en', 'es', 'nl', 'ko', 'it', 'de', 'th', 'ru', 'pt', 'pl', 'id', 'zh', 'sv', 'cs', 'ja', 'fr', 'ro', 'tr', 'ca', 'hu', 'uk', 'el', 'bg', 'ar', 'sr', 'mk', 'lv', 'sl', 'hi', 'gl', 'da', 'ur', 'sk', 'he', 'fi', 'az', 'lt', 'et', 'nn', 'cy', 'pa', 'af', 'fa', 'eu', 'vi', 'bn', 'ne', 'mr', 'be', 'kk', 'hy', 'sw', 'ta', 'sq')

# Used for identifying the platform running Alpaca.
class Platforms:
    windows: str = "win32"
    mac_os: str = "darwin"
    linux: str = "linux"

    # Platforms Alpaca is ported to, but does not fully support yet.
    ported: "tuple[str]" = (mac_os, windows)


# Folders Alpaca uses for its operation.
class AlpacaFolders:
    tmp_dir = os.path.join("/", "tmp", "alpaca")
    website_temp: str = os.path.join(tmp_dir, "websites")

    # extensions for paths are only meant to be used with a root path to be
    # concatenated with simultaneously
    youtube_temp_ext: str = "tmp/youtube"
    ollama_temp_ext: str = "tmp/ollama"
    images_temp_ext: str = "tmp/images"
