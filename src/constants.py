# constants.py
"""
Holds a few constant values that can be re-used all over the application.
"""

import os

# Big thanks to everyone contributing translations.
# These translators will be shown inside of the app under
# "About Alpaca" > "Contributors".
TRANSLATORS = [
    "Alex K (Russian) https://github.com/alexkdeveloper",
    "DasHi (Russian) https://github.com/col83",
    "Jeffry Samuel (Spanish) https://github.com/jeffser",
    "Louis Chauvet-Villaret (French) https://github.com/loulou64490",
    "Théo FORTIN (French) https://github.com/topiga",
    "Daimar Stein (Brazilian Portuguese) https://github.com/not-a-dev-stein",
    "Bruno Antunes (Brazilian Portuguese) https://github.com/antun3s",
    "Lucas Loura (Brazilian Portuguese) https://github.com/lloura",
    "CounterFlow64 (Norwegian) https://github.com/CounterFlow64",
    "Aritra Saha (Bengali) https://github.com/olumolu",
    "Yuehao Sui (Simplified Chinese) https://github.com/8ar10der",
    "Aleksana (Simplified Chinese) https://github.com/Aleksanaa",
    "Aritra Saha (Hindi) https://github.com/olumolu",
    "YusaBecerikli (Turkish) https://github.com/YusaBecerikli",
    "Simon (Ukrainian) https://github.com/OriginalSimon",
    "Marcel Margenberg (German) https://github.com/MehrzweckMandala",
    "Magnus Schlinsog (German) https://github.com/mags0ft",
    "Yosef Or Boczko (Hebrew) https://github.com/yoseforb",
    "Aryan Karamtoth (Telugu) https://github.com/SpaciousCoder78",
    "Edoardo Brogiolo (Italian) https://github.com/edo0",
    "Shidore (Japanese) https://github.com/sh1d0re",
    "Henk Leerssen (Dutch) https://github.com/Henkster72",
    "Nofal Briansah (Indonesian) https://github.com/nofalbriansah",
    "Harimanish (Tamil) https://github.com/harimanish",
    "Ekaterine Papava (Georgian) https://github.com/EkaterinePapava",
    "Jeethan Roche (Kannada) https://github.com/roche-jeethan",
    "Ahmed Najmawi (Arabic) https://github.com/x9a",
    "Aliaksandr Kliujeŭ (Belarusian) https://github.com/PlagaMedicum",
    "Athmane MOKRAOUI (Kabyle) https://github.com/BoFFire",
    "MoonShadow (Kabyle) https://github.com/ZiriSut"
]

# Used to populate SR language in preferences
SPEACH_RECOGNITION_LANGUAGES = (
    'en',
    'es',
    'nl',
    'ko',
    'it',
    'de',
    'th',
    'ru',
    'pt',
    'pl',
    'id',
    'zh',
    'sv',
    'cs',
    'ja',
    'fr',
    'ro',
    'tr',
    'ca',
    'hu',
    'uk',
    'el',
    'bg',
    'ar',
    'sr',
    'mk',
    'lv',
    'sl',
    'hi',
    'gl',
    'da',
    'ur',
    'sk',
    'he',
    'fi',
    'az',
    'lt',
    'et',
    'nn',
    'cy',
    'pa',
    'af',
    'fa',
    'eu',
    'vi',
    'bn',
    'ne',
    'mr',
    'be',
    'kk',
    'hy',
    'sw',
    'ta',
    'sq'
)

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

REMBG_MODELS = {
    'u2netp': {
        'display_name': 'U2Net Light',
        'size': '~5 MB',
        'link': 'https://github.com/xuebinqin/U-2-Net',
        'author': 'Xuebin Qin'
    },
    'u2net_human_seg': {
        'display_name': 'U2Net Human Trained',
        'size': '~168 MB',
        'link': 'https://github.com/xuebinqin/U-2-Net',
        'author': 'Xuebin Qin'
    },
    'silueta': {
        'display_name': 'Silueta',
        'size': '~45 MB',
        'link': 'https://github.com/xuebinqin/U-2-Net/issues/295',
        'author': 'Xuebin Qin'
    },
    'isnet-general-use': {
        'display_name': 'Isnet General Use',
        'size': '~170 MB',
        'link': 'https://github.com/xuebinqin/DIS',
        'author': 'Xuebin Qin'
    },
    'isnet-anime': {
        'display_name': 'Isnet Anime',
        'size': '~170 MB',
        'link': 'https://github.com/SkyTNT/anime-segmentation',
        'author': 'SkyTNT'
    }
}

SAMPLE_PROMPTS = [
    "What can you do?",
    "Give me a pancake recipe",
    "Why is the sky blue?",
    "Can you tell me a joke?",
    "Give me a healthy breakfast recipe",
    "How to make a pizza",
    "Can you write a poem?",
    "Can you write a story?",
    "What is GNU-Linux?",
    "Which is the best Linux distro?",
    "Give me butter chicken recipe",
    "Why is Pluto not a planet?",
    "What is a black-hole?",
    "Tell me how to stay fit",
    "Write a conversation between sun and Earth",
    "Why is the grass green?",
    "Write an Haïku about AI",
    "What is the meaning of life?",
    "Explain quantum physics in simple terms",
    "Explain the theory of relativity",
    "Explain how photosynthesis works",
    "Recommend a film about nature",
    "What is nostalgia?",
    "Can you explain time dilation in physics?",
    "Explain the basics of machine learning",
    "What is photoelectric effect?",
    "What's the history of the Great Wall of China?",
    "Tell me some historical facts about Taj Mahal",
    "Write a love story",
    "Write Schrödinger's equation in LaTeX",
    "Write the field equation in LaTeX",
    "What is confirmation bias?",
    "Tell me about your day",
    "How to create a strong password",
    "Explain how sodium batteries work",
    "Prove Euler's identity"
]

MODEL_CATEGORIES_METADATA = {
    'multilingual': {'name': _('Multilingual'), 'css': ['accent'], 'icon': 'language-symbolic'},
    'code': {'name': _('Code'), 'css': ['accent'], 'icon': 'code-symbolic'},
    'math': {'name': _('Math'), 'css': ['accent'], 'icon': 'accessories-calculator-symbolic'},
    'vision': {'name': _('Vision'), 'css': ['accent'], 'icon': 'eye-open-negative-filled-symbolic'},
    'embedding': {'name': _('Embedding'), 'css': ['error'], 'icon': 'brain-augemnted-symbolic'},
    'tools': {'name': _('Tools'), 'css': ['accent'], 'icon': 'wrench-wide-symbolic'},
    'reasoning': {'name': _('Reasoning'), 'css': ['accent'], 'icon': 'brain-augemnted-symbolic'},
    'cloud': {'name': _('Cloud'), 'css': ['accent'], 'icon': 'cloud-filled-symbolic'},
    'small': {'name': _('Small'), 'css': ['success'], 'icon': 'leaf-symbolic'},
    'medium': {'name': _('Medium'), 'css': ['brown'], 'icon': 'sprout-symbolic'},
    'big': {'name': _('Big'), 'css': ['warning'], 'icon': 'tree-circle-symbolic'},
    'huge': {'name': _('Huge'), 'css': ['error'], 'icon': 'weight-symbolic'},
    'language': {'css': [], 'icon': 'language-symbolic'}
}

# The identifier when inside the Flatpak runtime
IN_FLATPAK = bool(os.getenv("FLATPAK_ID"))

TITLE_GENERATION_PROMPT_OLLAMA = (
    "You are an assistant that generates short chat titles based on the "
    "prompt. If you want to, you can add a single emoji."
)
TITLE_GENERATION_PROMPT_OPENAI = (
    "You are an assistant that generates short chat titles based on the first "
    "message from a user. If you want to, you can add a single emoji."
)
MAX_TOKENS_TITLE_GENERATION = 31

def get_xdg_home(env, default):
    if IN_FLATPAK:
        return os.getenv(env)
    base = os.getenv(env) or os.path.expanduser(default)
    path = os.path.join(base, "com.jeffser.Alpaca")
    if not os.path.exists(path):
        os.makedirs(path)
    return path


data_dir = get_xdg_home("XDG_DATA_HOME", "~/.local/share")
config_dir = get_xdg_home("XDG_CONFIG_HOME", "~/.config")
cache_dir = get_xdg_home("XDG_CACHE_HOME", "~/.cache")

source_dir = os.path.abspath(os.path.dirname(__file__))

