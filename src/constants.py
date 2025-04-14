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

# Japanese and Chinese require additional library, maybe later
TTS_VOICES = {
    '🇺🇸 Heart': 'af_heart',
    '🇺🇸 Alloy': 'af_alloy',
    '🇺🇸 Aoede': 'af_aoede',
    '🇺🇸 Bella': 'af_bella',
    '🇺🇸 Jessica': 'af_jessica',
    '🇺🇸 Kore': 'af_kore',
    '🇺🇸 Nicole': 'af_nicole',
    '🇺🇸 Nova': 'af_nova',
    '🇺🇸 River': 'af_river',
    '🇺🇸 Sarah': 'af_sarah',
    '🇺🇸 Sky': 'af_sky',
    '🇺🇸 Adam': 'am_adam',
    '🇺🇸 Echo': 'am_echo',
    '🇺🇸 Eric': 'am_eric',
    '🇺🇸 Fenrir': 'am_fenrir',
    '🇺🇸 Liam': 'am_liam',
    '🇺🇸 Michael': 'am_michael',
    '🇺🇸 Onyx': 'am_onyx',
    '🇺🇸 Puck': 'am_puck',
    '🇺🇸 Santa': 'am_santa',
    '🇬🇧 Alice': 'bf_alice',
    '🇬🇧 Emma': 'bf_emma',
    '🇬🇧 Isabella': 'bf_isabella',
    '🇬🇧 Lily': 'bf_lily',
    '🇬🇧 Daniel': 'bm_daniel',
    '🇬🇧 Fable': 'bm_fable',
    '🇬🇧 George': 'bm_george',
    '🇬🇧 Lewis': 'bm_lewis',
    #'🇯🇵 Alpha': 'jf_alpha',
    #'🇯🇵 Gongitsune': 'jf_gongitsune',
    #'🇯🇵 Nezumi': 'jf_nezumi',
    #'🇯🇵 Tebukuro': 'jf_tebukuro',
    #'🇯🇵 Kumo': 'jm_kumo',
    #'🇨🇳 Xiaobei': 'zf_xiaobei',
    #'🇨🇳 Xiaoni': 'zf_xiaoni',
    #'🇨🇳 Xiaoxiao': 'zf_xiaoxiao',
    #'🇨🇳 Xiaoyi': 'zf_xiaoyi',
    #'🇨🇳 Yunjian': 'zm_yunjian',
    #'🇨🇳 Yunxi': 'zm_yunxi',
    #'🇨🇳 Yunxia': 'zm_yunxia',
    #'🇨🇳 Yunyang': 'zm_yunyang',
    '🇪🇸 Dora': 'ef_dora',
    '🇪🇸 Alex': 'em_alex',
    '🇪🇸 Santa': 'em_santa',
    '🇫🇷 Siwis': 'ff_siwis',
    '🇮🇳 Alpha': 'hf_alpha',
    '🇮🇳 Beta': 'hf_beta',
    '🇮🇳 Omega': 'hm_omega',
    '🇮🇳 Psi': 'hm_psi',
    '🇮🇹 Sara': 'if_sara',
    '🇮🇹 Nicola': 'im_nicola',
    '🇵🇹 Dora': 'pf_dora',
    '🇵🇹 Alex': 'pm_alex',
    '🇵🇹 Santa': 'pm_santa'
}

STT_MODELS = {
    'tiny': '~75 MB',
    'base': '~151 MB',
    'small': '~488 MB',
    'medium': '~1.5 GB',
    'large': '~2.9 GB'
}

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
