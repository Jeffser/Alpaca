# -*- coding: utf-8 -*-
from gettext import gettext as _

OLLAMA_MODELS = {
    "llama3.3": {
        "url": "https://ollama.com/library/llama3.3",
        "tags": [
                [
                        "latest",
                        "43 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "tools",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en",
                "de",
                "fr",
                "it",
                "pt",
                "hi",
                "es",
                "th"
        ],
        "description": _("New state of the art 70B model. Llama 3.3 70B offers similar performance compared to the Llama 3.1 405B model."),
    },
    "qwq": {
        "url": "https://ollama.com/library/qwq",
        "tags": [
                [
                        "latest",
                        "20 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ]
        ],
        "author": "Qwen Team",
        "categories": [
                "tools",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("QwQ is the reasoning model of the Qwen series."),
    },
    "llama3.2-vision": {
        "url": "https://ollama.com/library/llama3.2-vision",
        "tags": [
                [
                        "latest",
                        "7.8 GB"
                ],
                [
                        "11b",
                        "7.8 GB"
                ],
                [
                        "90b",
                        "55 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "vision",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Llama 3.2 Vision is a collection of instruction-tuned image reasoning generative models in 11B and 90B sizes."),
    },
    "llama3.2": {
        "url": "https://ollama.com/library/llama3.2",
        "tags": [
                [
                        "latest",
                        "2.0 GB"
                ],
                [
                        "1b",
                        "1.3 GB"
                ],
                [
                        "3b",
                        "2.0 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "multilingual"
        ],
        "languages": [
                "en",
                "de",
                "fr",
                "it",
                "pt",
                "hi",
                "es",
                "th"
        ],
        "description": _("Meta's Llama 3.2 goes small with 1B and 3B models."),
    },
    "llama3.1": {
        "url": "https://ollama.com/library/llama3.1",
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ],
                [
                        "405b",
                        "243 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "tools",
                "small",
                "medium",
                "huge",
                "math",
                "multilingual",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Llama 3.1 is a new state-of-the-art model from Meta available in 8B, 70B and 405B parameter sizes."),
    },
    "llama3": {
        "url": "https://ollama.com/library/llama3",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Meta Llama 3: The most capable openly available LLM to date"),
    },
    "mistral": {
        "url": "https://ollama.com/library/mistral",
        "tags": [
                [
                        "latest",
                        "4.4 GB"
                ],
                [
                        "7b",
                        "4.4 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "tools",
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("The 7B model released by Mistral AI, updated to version 0.3."),
    },
    "nomic-embed-text": {
        "url": "https://ollama.com/library/nomic-embed-text",
        "tags": [
                [
                        "latest",
                        "274 MB"
                ],
                [
                        "v1.5",
                        "274 MB"
                ]
        ],
        "author": "Nomic AI",
        "categories": [
                "small",
                "medium",
                "embedding",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A high-performing open embedding model with a large token context window."),
    },
    "gemma": {
        "url": "https://ollama.com/library/gemma",
        "tags": [
                [
                        "latest",
                        "5.0 GB"
                ],
                [
                        "2b",
                        "1.7 GB"
                ],
                [
                        "7b",
                        "5.0 GB"
                ]
        ],
        "author": "Google DeepMind",
        "categories": [
                "medium",
                "small",
                "big",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Gemma is a family of lightweight, state-of-the-art open models built by Google DeepMind. Updated to version 1.1"),
    },
    "qwen": {
        "url": "https://ollama.com/library/qwen",
        "tags": [
                [
                        "latest",
                        "2.3 GB"
                ],
                [
                        "0.5b",
                        "395 MB"
                ],
                [
                        "1.8b",
                        "1.1 GB"
                ],
                [
                        "4b",
                        "2.3 GB"
                ],
                [
                        "7b",
                        "4.5 GB"
                ],
                [
                        "14b",
                        "8.2 GB"
                ],
                [
                        "32b",
                        "18 GB"
                ],
                [
                        "72b",
                        "41 GB"
                ],
                [
                        "110b",
                        "63 GB"
                ]
        ],
        "author": "Alibaba",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code",
                "math",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("Qwen 1.5 is a series of large language models by Alibaba Cloud spanning from 0.5B to 110B parameters"),
    },
    "qwen2": {
        "url": "https://ollama.com/library/qwen2",
        "tags": [
                [
                        "latest",
                        "4.4 GB"
                ],
                [
                        "0.5b",
                        "352 MB"
                ],
                [
                        "1.5b",
                        "935 MB"
                ],
                [
                        "7b",
                        "4.4 GB"
                ],
                [
                        "72b",
                        "41 GB"
                ]
        ],
        "author": "Alibaba",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "huge",
                "multilingual"
        ],
        "languages": [
                "de",
                "fr",
                "es",
                "pt",
                "it",
                "nl",
                "ru",
                "cs",
                "pl",
                "ar",
                "fa",
                "he",
                "tr",
                "ja",
                "ko",
                "vi",
                "th",
                "id",
                "ms",
                "lo",
                "my",
                "ceb",
                "km",
                "tl",
                "hi",
                "bn",
                "ur"
        ],
        "description": _("Qwen2 is a new series of large language models from Alibaba group"),
    },
    "phi3": {
        "url": "https://ollama.com/library/phi3",
        "tags": [
                [
                        "latest",
                        "2.2 GB"
                ],
                [
                        "3.8b",
                        "2.2 GB"
                ],
                [
                        "14b",
                        "7.9 GB"
                ]
        ],
        "author": "Microsoft",
        "categories": [
                "small",
                "medium",
                "big",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Phi-3 is a family of lightweight 3B (Mini) and 14B (Medium) state-of-the-art open models by Microsoft."),
    },
    "llama2": {
        "url": "https://ollama.com/library/llama2",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "small",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Llama 2 is a collection of foundation language models ranging from 7B to 70B parameters."),
    },
    "qwen2.5": {
        "url": "https://ollama.com/library/qwen2.5",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "0.5b",
                        "398 MB"
                ],
                [
                        "1.5b",
                        "986 MB"
                ],
                [
                        "3b",
                        "1.9 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ],
                [
                        "14b",
                        "9.0 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ],
                [
                        "72b",
                        "47 GB"
                ]
        ],
        "author": "Alibaba",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh",
                "fr",
                "es",
                "pt",
                "de",
                "it",
                "ru",
                "ja",
                "ko",
                "vi",
                "th",
                "ar"
        ],
        "description": _("Qwen2.5 models are pretrained on Alibaba's latest large-scale dataset, encompassing up to 18 trillion tokens. The model supports up to 128K tokens and has multilingual support."),
    },
    "gemma2": {
        "url": "https://ollama.com/library/gemma2",
        "tags": [
                [
                        "latest",
                        "5.4 GB"
                ],
                [
                        "2b",
                        "1.6 GB"
                ],
                [
                        "9b",
                        "5.4 GB"
                ],
                [
                        "27b",
                        "16 GB"
                ]
        ],
        "author": "Google DeepMind",
        "categories": [
                "medium",
                "small",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Google Gemma 2 is a high-performing and efficient model available in three sizes: 2B, 9B, and 27B."),
    },
    "llava": {
        "url": "https://ollama.com/library/llava",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ],
                [
                        "13b",
                        "8.0 GB"
                ],
                [
                        "34b",
                        "20 GB"
                ]
        ],
        "author": "Haotian Liu",
        "categories": [
                "vision",
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("🌋 LLaVA is a novel end-to-end trained large multimodal model that combines a vision encoder and Vicuna for general-purpose visual and language understanding. Updated to version 1.6."),
    },
    "codellama": {
        "url": "https://ollama.com/library/codellama",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "34b",
                        "19 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A large language model that can use text prompts to generate and discuss code."),
    },
    "qwen2.5-coder": {
        "url": "https://ollama.com/library/qwen2.5-coder",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "0.5b",
                        "398 MB"
                ],
                [
                        "1.5b",
                        "986 MB"
                ],
                [
                        "3b",
                        "1.9 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ],
                [
                        "14b",
                        "9.0 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ]
        ],
        "author": "Alibaba",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("The latest series of Code-Specific Qwen models, with significant improvements in code generation, code reasoning, and code fixing."),
    },
    "mistral-nemo": {
        "url": "https://ollama.com/library/mistral-nemo",
        "tags": [
                [
                        "latest",
                        "7.1 GB"
                ],
                [
                        "12b",
                        "7.1 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "tools",
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A state-of-the-art 12B model with 128k context length, built by Mistral AI in collaboration with NVIDIA."),
    },
    "tinyllama": {
        "url": "https://ollama.com/library/tinyllama",
        "tags": [
                [
                        "latest",
                        "638 MB"
                ],
                [
                        "1.1b",
                        "638 MB"
                ]
        ],
        "author": "TinyLlama Team",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("The TinyLlama project is an open endeavor to train a compact 1.1B Llama model on 3 trillion tokens."),
    },
    "mxbai-embed-large": {
        "url": "https://ollama.com/library/mxbai-embed-large",
        "tags": [
                [
                        "latest",
                        "670 MB"
                ],
                [
                        "335m",
                        "670 MB"
                ]
        ],
        "author": "Mixedbread.ai",
        "categories": [
                "small",
                "medium",
                "embedding"
        ],
        "languages": [
                "en"
        ],
        "description": _("State-of-the-art large embedding model from mixedbread.ai"),
    },
    "starcoder2": {
        "url": "https://ollama.com/library/starcoder2",
        "tags": [
                [
                        "latest",
                        "1.7 GB"
                ],
                [
                        "3b",
                        "1.7 GB"
                ],
                [
                        "7b",
                        "4.0 GB"
                ],
                [
                        "15b",
                        "9.1 GB"
                ]
        ],
        "author": "BigCode",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("StarCoder2 is the next generation of transparently trained open code LLMs that comes in three sizes: 3B, 7B and 15B parameters."),
    },
    "mixtral": {
        "url": "https://ollama.com/library/mixtral",
        "tags": [
                [
                        "latest",
                        "26 GB"
                ],
                [
                        "8x7b",
                        "26 GB"
                ],
                [
                        "8x22b",
                        "80 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "tools",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A set of Mixture of Experts (MoE) model with open weights by Mistral AI in 8x7b and 8x22b parameter sizes."),
    },
    "dolphin-mixtral": {
        "url": "https://ollama.com/library/dolphin-mixtral",
        "tags": [
                [
                        "latest",
                        "26 GB"
                ],
                [
                        "8x7b",
                        "26 GB"
                ],
                [
                        "8x22b",
                        "80 GB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Uncensored, 8x7b and 8x22b fine-tuned models based on the Mixtral mixture of experts models that excels at coding tasks. Created by Eric Hartford."),
    },
    "codegemma": {
        "url": "https://ollama.com/library/codegemma",
        "tags": [
                [
                        "latest",
                        "5.0 GB"
                ],
                [
                        "2b",
                        "1.6 GB"
                ],
                [
                        "7b",
                        "5.0 GB"
                ]
        ],
        "author": "Google DeepMind",
        "categories": [
                "medium",
                "small",
                "big",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("CodeGemma is a collection of powerful, lightweight models that can perform a variety of coding tasks like fill-in-the-middle code completion, code generation, natural language understanding, mathematical reasoning, and instruction following."),
    },
    "deepseek-coder-v2": {
        "url": "https://ollama.com/library/deepseek-coder-v2",
        "tags": [
                [
                        "latest",
                        "8.9 GB"
                ],
                [
                        "16b",
                        "8.9 GB"
                ],
                [
                        "236b",
                        "133 GB"
                ]
        ],
        "author": "DeepSeek Team",
        "categories": [
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("An open-source Mixture-of-Experts code language model that achieves performance comparable to GPT4-Turbo in code-specific tasks."),
    },
    "phi": {
        "url": "https://ollama.com/library/phi",
        "tags": [
                [
                        "latest",
                        "1.6 GB"
                ],
                [
                        "2.7b",
                        "1.6 GB"
                ]
        ],
        "author": "Microsoft",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("Phi-2: a 2.7B language model by Microsoft Research that demonstrates outstanding reasoning and language understanding capabilities."),
    },
    "llama2-uncensored": {
        "url": "https://ollama.com/library/llama2-uncensored",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "George Sung, Jarrad Hope",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Uncensored Llama 2 model by George Sung and Jarrad Hope."),
    },
    "deepseek-coder": {
        "url": "https://ollama.com/library/deepseek-coder",
        "tags": [
                [
                        "latest",
                        "776 MB"
                ],
                [
                        "1.3b",
                        "776 MB"
                ],
                [
                        "6.7b",
                        "3.8 GB"
                ],
                [
                        "33b",
                        "19 GB"
                ]
        ],
        "author": "DeepSeek Team",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("DeepSeek Coder is a capable coding model trained on two trillion code and natural language tokens."),
    },
    "snowflake-arctic-embed": {
        "url": "https://ollama.com/library/snowflake-arctic-embed",
        "tags": [
                [
                        "latest",
                        "669 MB"
                ],
                [
                        "22m",
                        "46 MB"
                ],
                [
                        "33m",
                        "67 MB"
                ],
                [
                        "110m",
                        "219 MB"
                ],
                [
                        "137m",
                        "274 MB"
                ],
                [
                        "335m",
                        "669 MB"
                ]
        ],
        "author": "Snowflake",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "embedding"
        ],
        "languages": [
                "en"
        ],
        "description": _("A suite of text embedding models by Snowflake, optimized for performance."),
    },
    "wizardlm2": {
        "url": "https://ollama.com/library/wizardlm2",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ],
                [
                        "8x22b",
                        "80 GB"
                ]
        ],
        "author": "Microsoft",
        "categories": [
                "small",
                "medium",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en"
        ],
        "description": _("State of the art large language model from Microsoft AI with improved performance on complex chat, multilingual, reasoning and agent use cases."),
    },
    "dolphin-mistral": {
        "url": "https://ollama.com/library/dolphin-mistral",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "small",
                "medium",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("The uncensored Dolphin model based on Mistral that excels at coding tasks. Updated to version 2.8."),
    },
    "dolphin-llama3": {
        "url": "https://ollama.com/library/dolphin-llama3",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "small",
                "medium",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Dolphin 2.9 is a new model with 8B and 70B sizes by Eric Hartford based on Llama 3 that has a variety of instruction, conversational, and coding skills."),
    },
    "yi": {
        "url": "https://ollama.com/library/yi",
        "tags": [
                [
                        "latest",
                        "3.5 GB"
                ],
                [
                        "6b",
                        "3.5 GB"
                ],
                [
                        "9b",
                        "5.0 GB"
                ],
                [
                        "34b",
                        "19 GB"
                ]
        ],
        "author": "01.AI",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("Yi 1.5 is a high-performing, bilingual language model."),
    },
    "command-r": {
        "url": "https://ollama.com/library/command-r",
        "tags": [
                [
                        "latest",
                        "19 GB"
                ],
                [
                        "35b",
                        "19 GB"
                ]
        ],
        "author": "Cohere",
        "categories": [
                "tools",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Command R is a Large Language Model optimized for conversational interaction and long context tasks."),
    },
    "orca-mini": {
        "url": "https://ollama.com/library/orca-mini",
        "tags": [
                [
                        "latest",
                        "2.0 GB"
                ],
                [
                        "3b",
                        "2.0 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "Orca Mini Team",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("A general-purpose model ranging from 3 billion parameters to 70 billion, suitable for entry-level hardware."),
    },
    "llava-llama3": {
        "url": "https://ollama.com/library/llava-llama3",
        "tags": [
                [
                        "latest",
                        "5.5 GB"
                ],
                [
                        "8b",
                        "5.5 GB"
                ]
        ],
        "author": "Xtuner",
        "categories": [
                "vision",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("A LLaVA model fine-tuned from Llama 3 Instruct with better scores in several benchmarks."),
    },
    "zephyr": {
        "url": "https://ollama.com/library/zephyr",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ],
                [
                        "141b",
                        "80 GB"
                ]
        ],
        "author": "Hugging Face H4",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Zephyr is a series of fine-tuned versions of the Mistral and Mixtral models that are trained to act as helpful assistants."),
    },
    "phi3.5": {
        "url": "https://ollama.com/library/phi3.5",
        "tags": [
                [
                        "latest",
                        "2.2 GB"
                ],
                [
                        "3.8b",
                        "2.2 GB"
                ]
        ],
        "author": "Microsoft",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A lightweight AI model with 3.8 billion parameters with performance overtaking similarly and larger sized models."),
    },
    "all-minilm": {
        "url": "https://ollama.com/library/all-minilm",
        "tags": [
                [
                        "latest",
                        "46 MB"
                ],
                [
                        "22m",
                        "46 MB"
                ],
                [
                        "33m",
                        "67 MB"
                ]
        ],
        "author": "Sentence Transformers",
        "categories": [
                "small",
                "medium",
                "big",
                "embedding"
        ],
        "languages": [
                "en"
        ],
        "description": _("Embedding models on very large sentence level datasets."),
    },
    "codestral": {
        "url": "https://ollama.com/library/codestral",
        "tags": [
                [
                        "latest",
                        "13 GB"
                ],
                [
                        "22b",
                        "13 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Codestral is Mistral AI’s first-ever code model designed for code generation tasks."),
    },
    "starcoder": {
        "url": "https://ollama.com/library/starcoder",
        "tags": [
                [
                        "latest",
                        "1.8 GB"
                ],
                [
                        "1b",
                        "726 MB"
                ],
                [
                        "3b",
                        "1.8 GB"
                ],
                [
                        "7b",
                        "4.3 GB"
                ],
                [
                        "15b",
                        "9.0 GB"
                ]
        ],
        "author": "BigCode",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("StarCoder is a code generation model trained on 80+ programming languages."),
    },
    "vicuna": {
        "url": "https://ollama.com/library/vicuna",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "33b",
                        "18 GB"
                ]
        ],
        "author": "lmsys.org",
        "categories": [
                "small",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("General use chat model based on Llama and Llama 2 with 2K to 16K context sizes."),
    },
    "granite-code": {
        "url": "https://ollama.com/library/granite-code",
        "tags": [
                [
                        "latest",
                        "2.0 GB"
                ],
                [
                        "3b",
                        "2.0 GB"
                ],
                [
                        "8b",
                        "4.6 GB"
                ],
                [
                        "20b",
                        "12 GB"
                ],
                [
                        "34b",
                        "19 GB"
                ]
        ],
        "author": "IBM for Code Intelligence",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A family of open foundation models by IBM for Code Intelligence"),
    },
    "mistral-openorca": {
        "url": "https://ollama.com/library/mistral-openorca",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Open Orca",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("Mistral OpenOrca is a 7 billion parameter model, fine-tuned on top of the Mistral 7B model using the OpenOrca dataset."),
    },
    "smollm": {
        "url": "https://ollama.com/library/smollm",
        "tags": [
                [
                        "latest",
                        "991 MB"
                ],
                [
                        "135m",
                        "92 MB"
                ],
                [
                        "360m",
                        "229 MB"
                ],
                [
                        "1.7b",
                        "991 MB"
                ]
        ],
        "author": "Hugging Face TB",
        "categories": [
                "small",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("🪐 A family of small models with 135M, 360M, and 1.7B parameters, trained on a new high-quality dataset."),
    },
    "wizard-vicuna-uncensored": {
        "url": "https://ollama.com/library/wizard-vicuna-uncensored",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "30b",
                        "18 GB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "small",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Wizard Vicuna Uncensored is a 7B, 13B, and 30B parameter model based on Llama 2 uncensored by Eric Hartford."),
    },
    "llama2-chinese": {
        "url": "https://ollama.com/library/llama2-chinese",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "small",
                "medium",
                "big",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("Llama 2 based model fine tuned to improve Chinese dialogue ability."),
    },
    "bge-m3": {
        "url": "https://ollama.com/library/bge-m3",
        "tags": [
                [
                        "latest",
                        "1.2 GB"
                ],
                [
                        "567m",
                        "1.2 GB"
                ]
        ],
        "author": "BGE-m3 Team",
        "categories": [
                "small",
                "medium",
                "embedding"
        ],
        "languages": [
                "en"
        ],
        "description": _("BGE-M3 is a new model from BAAI distinguished for its versatility in Multi-Functionality, Multi-Linguality, and Multi-Granularity."),
    },
    "codegeex4": {
        "url": "https://ollama.com/library/codegeex4",
        "tags": [
                [
                        "latest",
                        "5.5 GB"
                ],
                [
                        "9b",
                        "5.5 GB"
                ]
        ],
        "author": "THUDM",
        "categories": [
                "medium",
                "big",
                "code",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("A versatile model for AI software development scenarios, including code completion."),
    },
    "openchat": {
        "url": "https://ollama.com/library/openchat",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "OpenChat Team",
        "categories": [
                "small",
                "medium",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A family of open-source models trained on a wide variety of data, surpassing ChatGPT on various benchmarks. Updated to version 3.5-0106."),
    },
    "aya": {
        "url": "https://ollama.com/library/aya",
        "tags": [
                [
                        "latest",
                        "4.8 GB"
                ],
                [
                        "8b",
                        "4.8 GB"
                ],
                [
                        "35b",
                        "20 GB"
                ]
        ],
        "author": "Cohere",
        "categories": [
                "small",
                "medium",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en"
        ],
        "description": _("Aya 23, released by Cohere, is a new family of state-of-the-art, multilingual models that support 23 languages."),
    },
    "codeqwen": {
        "url": "https://ollama.com/library/codeqwen",
        "tags": [
                [
                        "latest",
                        "4.2 GB"
                ],
                [
                        "7b",
                        "4.2 GB"
                ]
        ],
        "author": "Alibaba",
        "categories": [
                "small",
                "medium",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("CodeQwen1.5 is a large language model pretrained on a large amount of code data."),
    },
    "nous-hermes2": {
        "url": "https://ollama.com/library/nous-hermes2",
        "tags": [
                [
                        "latest",
                        "6.1 GB"
                ],
                [
                        "10.7b",
                        "6.1 GB"
                ],
                [
                        "34b",
                        "19 GB"
                ]
        ],
        "author": "Nous Research",
        "categories": [
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("The powerful family of models by Nous Research that excels at scientific discussion and coding tasks."),
    },
    "command-r-plus": {
        "url": "https://ollama.com/library/command-r-plus",
        "tags": [
                [
                        "latest",
                        "59 GB"
                ],
                [
                        "104b",
                        "59 GB"
                ]
        ],
        "author": "Cohere",
        "categories": [
                "tools",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Command R+ is a powerful, scalable large language model purpose-built to excel at real-world enterprise use cases."),
    },
    "wizardcoder": {
        "url": "https://ollama.com/library/wizardcoder",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "33b",
                        "19 GB"
                ]
        ],
        "author": "WizardLM Team",
        "categories": [
                "small",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("State-of-the-art code generation model"),
    },
    "stable-code": {
        "url": "https://ollama.com/library/stable-code",
        "tags": [
                [
                        "latest",
                        "1.6 GB"
                ],
                [
                        "3b",
                        "1.6 GB"
                ]
        ],
        "author": "Stability AI",
        "categories": [
                "small",
                "medium",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Stable Code 3B is a coding model with instruct and code completion variants on par with models such as Code Llama 7B that are 2.5x larger."),
    },
    "tinydolphin": {
        "url": "https://ollama.com/library/tinydolphin",
        "tags": [
                [
                        "latest",
                        "637 MB"
                ],
                [
                        "1.1b",
                        "637 MB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("An experimental 1.1B parameter model trained on the new Dolphin 2.8 dataset by Eric Hartford and based on TinyLlama."),
    },
    "openhermes": {
        "url": "https://ollama.com/library/openhermes",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "v2",
                        "4.1 GB"
                ],
                [
                        "v2.5",
                        "4.1 GB"
                ]
        ],
        "author": "Teknium",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("OpenHermes 2.5 is a 7B model fine-tuned by Teknium on Mistral with fully open datasets."),
    },
    "mistral-large": {
        "url": "https://ollama.com/library/mistral-large",
        "tags": [
                [
                        "latest",
                        "73 GB"
                ],
                [
                        "123b",
                        "73 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "tools",
                "huge",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Mistral Large 2 is Mistral's new flagship model that is significantly more capable in code generation, mathematics, and reasoning with 128k context window and support for dozens of languages."),
    },
    "qwen2-math": {
        "url": "https://ollama.com/library/qwen2-math",
        "tags": [
                [
                        "latest",
                        "4.4 GB"
                ],
                [
                        "1.5b",
                        "935 MB"
                ],
                [
                        "7b",
                        "4.4 GB"
                ],
                [
                        "72b",
                        "41 GB"
                ]
        ],
        "author": "Alibaba",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Qwen2 Math is a series of specialized math language models built upon the Qwen2 LLMs, which significantly outperforms the mathematical capabilities of open-source models and even closed-source models (e.g., GPT4o)."),
    },
    "glm4": {
        "url": "https://ollama.com/library/glm4",
        "tags": [
                [
                        "latest",
                        "5.5 GB"
                ],
                [
                        "9b",
                        "5.5 GB"
                ]
        ],
        "author": "THUDM",
        "categories": [
                "medium",
                "big",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("A strong multi-lingual general language model with competitive performance to Llama 3."),
    },
    "stablelm2": {
        "url": "https://ollama.com/library/stablelm2",
        "tags": [
                [
                        "latest",
                        "983 MB"
                ],
                [
                        "1.6b",
                        "983 MB"
                ],
                [
                        "12b",
                        "7.0 GB"
                ]
        ],
        "author": "Stability AI",
        "categories": [
                "small",
                "medium",
                "big",
                "multilingual"
        ],
        "languages": [
                "en",
                "es",
                "de",
                "it",
                "fr",
                "pt",
                "nl"
        ],
        "description": _("Stable LM 2 is a state-of-the-art 1.6B and 12B parameter language model trained on multilingual data in English, Spanish, German, Italian, French, Portuguese, and Dutch."),
    },
    "bakllava": {
        "url": "https://ollama.com/library/bakllava",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ]
        ],
        "author": "Skunkworks AI",
        "categories": [
                "vision",
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("BakLLaVA is a multimodal model consisting of the Mistral 7B base model augmented with the LLaVA architecture."),
    },
    "reflection": {
        "url": "https://ollama.com/library/reflection",
        "tags": [
                [
                        "latest",
                        "40 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Matt Shumer",
        "categories": [
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A high-performing model trained with a new technique called Reflection-tuning that teaches a LLM to detect mistakes in its reasoning and correct course."),
    },
    "deepseek-llm": {
        "url": "https://ollama.com/library/deepseek-llm",
        "tags": [
                [
                        "latest",
                        "4.0 GB"
                ],
                [
                        "7b",
                        "4.0 GB"
                ],
                [
                        "67b",
                        "38 GB"
                ]
        ],
        "author": "DeepSeek Team",
        "categories": [
                "small",
                "medium",
                "huge",
                "multilingual",
                "code",
                "math"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("An advanced language model crafted with 2 trillion bilingual tokens."),
    },
    "llama3-gradient": {
        "url": "https://ollama.com/library/llama3-gradient",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Gradient AI",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("This model extends LLama-3 8B's context length from 8k to over 1m tokens."),
    },
    "wizard-math": {
        "url": "https://ollama.com/library/wizard-math",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "WizardLM Team",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Model focused on math and logic problems"),
    },
    "moondream": {
        "url": "https://ollama.com/library/moondream",
        "tags": [
                [
                        "latest",
                        "1.7 GB"
                ],
                [
                        "1.8b",
                        "1.7 GB"
                ]
        ],
        "author": "Vikhyatk",
        "categories": [
                "vision",
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("moondream2 is a small vision language model designed to run efficiently on edge devices."),
    },
    "neural-chat": {
        "url": "https://ollama.com/library/neural-chat",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Intel",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A fine-tuned model based on Mistral with good coverage of domain and language."),
    },
    "llama3-chatqa": {
        "url": "https://ollama.com/library/llama3-chatqa",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Nvidia",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A model from NVIDIA based on Llama 3 that excels at conversational question answering (QA) and retrieval-augmented generation (RAG)."),
    },
    "xwinlm": {
        "url": "https://ollama.com/library/xwinlm",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Xwin LM",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("Conversational model based on Llama 2 that performs competitively on various benchmarks."),
    },
    "sqlcoder": {
        "url": "https://ollama.com/library/sqlcoder",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ],
                [
                        "15b",
                        "9.0 GB"
                ]
        ],
        "author": "Defog.ai",
        "categories": [
                "small",
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("SQLCoder is a code completion model fined-tuned on StarCoder for SQL generation tasks"),
    },
    "nous-hermes": {
        "url": "https://ollama.com/library/nous-hermes",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Nous Research",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("General use models based on Llama and Llama 2 from Nous Research."),
    },
    "phind-codellama": {
        "url": "https://ollama.com/library/phind-codellama",
        "tags": [
                [
                        "latest",
                        "19 GB"
                ],
                [
                        "34b",
                        "19 GB"
                ]
        ],
        "author": "Phind",
        "categories": [
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Code generation model based on Code Llama."),
    },
    "yarn-llama2": {
        "url": "https://ollama.com/library/yarn-llama2",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Nous Research",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("An extension of Llama 2 that supports a context of up to 128k tokens."),
    },
    "dolphincoder": {
        "url": "https://ollama.com/library/dolphincoder",
        "tags": [
                [
                        "latest",
                        "4.2 GB"
                ],
                [
                        "7b",
                        "4.2 GB"
                ],
                [
                        "15b",
                        "9.1 GB"
                ]
        ],
        "author": "Cognitive Computations",
        "categories": [
                "small",
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A 7B and 15B uncensored variant of the Dolphin model family that excels at coding, based on StarCoder2."),
    },
    "wizardlm": {
        "url": "https://ollama.com/library/wizardlm",
        "tags": [
                [
                        "7b-q2_K",
                        "2.8 GB"
                ],
                [
                        "7b-q3_K_S",
                        "2.9 GB"
                ],
                [
                        "7b-q3_K_M",
                        "3.3 GB"
                ]
        ],
        "author": "WizardLM Team",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("General use model based on Llama 2."),
    },
    "deepseek-v2": {
        "url": "https://ollama.com/library/deepseek-v2",
        "tags": [
                [
                        "latest",
                        "8.9 GB"
                ],
                [
                        "16b",
                        "8.9 GB"
                ],
                [
                        "236b",
                        "133 GB"
                ]
        ],
        "author": "DeepSeek Team",
        "categories": [
                "medium",
                "big",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("A strong, economical, and efficient Mixture-of-Experts language model."),
    },
    "starling-lm": {
        "url": "https://ollama.com/library/starling-lm",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Berkeley Nest",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("Starling is a large language model trained by reinforcement learning from AI feedback focused on improving chatbot helpfulness."),
    },
    "samantha-mistral": {
        "url": "https://ollama.com/library/samantha-mistral",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A companion assistant trained in philosophy, psychology, and personal relationships. Based on Mistral."),
    },
    "hermes3": {
        "url": "https://ollama.com/library/hermes3",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "3b",
                        "2.0 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ],
                [
                        "405b",
                        "229 GB"
                ]
        ],
        "author": "Nous Research ",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Hermes 3 is the latest version of the flagship Hermes series of LLMs by Nous Research"),
    },
    "yi-coder": {
        "url": "https://ollama.com/library/yi-coder",
        "tags": [
                [
                        "latest",
                        "5.0 GB"
                ],
                [
                        "1.5b",
                        "866 MB"
                ],
                [
                        "9b",
                        "5.0 GB"
                ]
        ],
        "author": "01.AI",
        "categories": [
                "medium",
                "small",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Yi-Coder is a series of open-source code language models that delivers state-of-the-art coding performance with fewer than 10 billion parameters."),
    },
    "falcon": {
        "url": "https://ollama.com/library/falcon",
        "tags": [
                [
                        "latest",
                        "4.2 GB"
                ],
                [
                        "7b",
                        "4.2 GB"
                ],
                [
                        "40b",
                        "24 GB"
                ],
                [
                        "180b",
                        "101 GB"
                ]
        ],
        "author": "Technology Innovation Institute",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A large language model built by the Technology Innovation Institute (TII) for use in summarization, text generation, and chat bots."),
    },
    "internlm2": {
        "url": "https://ollama.com/library/internlm2",
        "tags": [
                [
                        "latest",
                        "4.5 GB"
                ],
                [
                        "1m",
                        "4.5 GB"
                ],
                [
                        "1.8b",
                        "1.1 GB"
                ],
                [
                        "7b",
                        "4.5 GB"
                ],
                [
                        "20b",
                        "11 GB"
                ]
        ],
        "author": "Intern LM",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("InternLM2.5 is a 7B parameter model tailored for practical scenarios with outstanding reasoning capability."),
    },
    "solar": {
        "url": "https://ollama.com/library/solar",
        "tags": [
                [
                        "latest",
                        "6.1 GB"
                ],
                [
                        "10.7b",
                        "6.1 GB"
                ]
        ],
        "author": "Upstage",
        "categories": [
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("A compact, yet powerful 10.7B large language model designed for single-turn conversation."),
    },
    "athene-v2": {
        "url": "https://ollama.com/library/athene-v2",
        "tags": [
                [
                        "latest",
                        "47 GB"
                ],
                [
                        "72b",
                        "47 GB"
                ]
        ],
        "author": "Nexusflow",
        "categories": [
                "tools",
                "huge",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Athene-V2 is a 72B parameter model which excels at code completion, mathematics, and log extraction tasks."),
    },
    "llava-phi3": {
        "url": "https://ollama.com/library/llava-phi3",
        "tags": [
                [
                        "latest",
                        "2.9 GB"
                ],
                [
                        "3.8b",
                        "2.9 GB"
                ]
        ],
        "author": "Xtuner",
        "categories": [
                "vision",
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A new small LLaVA model fine-tuned from Phi 3 Mini."),
    },
    "orca2": {
        "url": "https://ollama.com/library/orca2",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Microsoft Research",
        "categories": [
                "small",
                "medium",
                "big",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Orca 2 is built by Microsoft research, and are a fine-tuned version of Meta's Llama 2 models. The model is designed to excel particularly in reasoning."),
    },
    "minicpm-v": {
        "url": "https://ollama.com/library/minicpm-v",
        "tags": [
                [
                        "latest",
                        "5.5 GB"
                ],
                [
                        "8b",
                        "5.5 GB"
                ]
        ],
        "author": "OpenBMB",
        "categories": [
                "vision",
                "medium",
                "big",
                "math",
                "multilingual",
                "code"
        ],
        "languages": [
                "en",
                "zh",
                "de",
                "fr",
                "it",
                "ko"
        ],
        "description": _("A series of multimodal LLMs (MLLMs) designed for vision-language understanding."),
    },
    "stable-beluga": {
        "url": "https://ollama.com/library/stable-beluga",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "Stability AI",
        "categories": [
                "small",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Llama 2 based model fine tuned on an Orca-style dataset. Originally called Free Willy."),
    },
    "mistral-small": {
        "url": "https://ollama.com/library/mistral-small",
        "tags": [
                [
                        "latest",
                        "14 GB"
                ],
                [
                        "22b",
                        "13 GB"
                ],
                [
                        "24b",
                        "14 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "tools",
                "big",
                "huge",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Mistral Small 3 sets a new benchmark in the “small” Large Language Models category below 70B."),
    },
    "dolphin-phi": {
        "url": "https://ollama.com/library/dolphin-phi",
        "tags": [
                [
                        "latest",
                        "1.6 GB"
                ],
                [
                        "2.7b",
                        "1.6 GB"
                ]
        ],
        "author": "Eric Hartford",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("2.7B uncensored Dolphin model by Eric Hartford, based on the Phi language model by Microsoft Research."),
    },
    "smollm2": {
        "url": "https://ollama.com/library/smollm2",
        "tags": [
                [
                        "latest",
                        "1.8 GB"
                ],
                [
                        "135m",
                        "271 MB"
                ],
                [
                        "360m",
                        "726 MB"
                ],
                [
                        "1.7b",
                        "1.8 GB"
                ]
        ],
        "author": "Hugging Face TB",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("SmolLM2 is a family of compact language models available in three size: 135M, 360M, and 1.7B parameters."),
    },
    "wizardlm-uncensored": {
        "url": "https://ollama.com/library/wizardlm-uncensored",
        "tags": [
                [
                        "latest",
                        "7.4 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "TheBloke AI",
        "categories": [
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("Uncensored version of Wizard LM model"),
    },
    "nemotron-mini": {
        "url": "https://ollama.com/library/nemotron-mini",
        "tags": [
                [
                        "latest",
                        "2.7 GB"
                ],
                [
                        "4b",
                        "2.7 GB"
                ]
        ],
        "author": "Nvidia",
        "categories": [
                "tools",
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A commercial-friendly small language model by NVIDIA optimized for roleplay, RAG QA, and function calling."),
    },
    "yarn-mistral": {
        "url": "https://ollama.com/library/yarn-mistral",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Nous Research",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("An extension of Mistral to support context windows of 64K or 128K."),
    },
    "llama-pro": {
        "url": "https://ollama.com/library/llama-pro",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "instruct",
                        "4.7 GB"
                ],
                [
                        "text",
                        "4.7 GB"
                ]
        ],
        "author": "Tencent",
        "categories": [
                "small",
                "medium",
                "big",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("An expansion of Llama 2 that specializes in integrating both general language understanding and domain-specific knowledge, particularly in programming and mathematics."),
    },
    "medllama2": {
        "url": "https://ollama.com/library/medllama2",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ]
        ],
        "author": "Siraj Raval",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("Fine-tuned Llama 2 model to answer medical questions based on an open source medical dataset."),
    },
    "meditron": {
        "url": "https://ollama.com/library/meditron",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ],
                [
                        "70b",
                        "39 GB"
                ]
        ],
        "author": "EPFL LLM Team",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Open-source medical large language model adapted from Llama 2 to the medical domain."),
    },
    "llama3-groq-tool-use": {
        "url": "https://ollama.com/library/llama3-groq-tool-use",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Groq",
        "categories": [
                "tools",
                "small",
                "medium",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A series of models from Groq that represent a significant advancement in open-source AI capabilities for tool use/function calling."),
    },
    "nemotron": {
        "url": "https://ollama.com/library/nemotron",
        "tags": [
                [
                        "latest",
                        "43 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ]
        ],
        "author": "Nvidia",
        "categories": [
                "tools",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Llama-3.1-Nemotron-70B-Instruct is a large language model customized by NVIDIA to improve the helpfulness of LLM generated responses to user queries."),
    },
    "nexusraven": {
        "url": "https://ollama.com/library/nexusraven",
        "tags": [
                [
                        "latest",
                        "7.4 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "NexusFlow AI",
        "categories": [
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("Nexus Raven is a 13B instruction tuned model for function calling tasks."),
    },
    "nous-hermes2-mixtral": {
        "url": "https://ollama.com/library/nous-hermes2-mixtral",
        "tags": [
                [
                        "latest",
                        "26 GB"
                ],
                [
                        "8x7b",
                        "26 GB"
                ]
        ],
        "author": "Nous Research",
        "categories": [
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("The Nous Hermes 2 model from Nous Research, now trained over Mixtral."),
    },
    "codeup": {
        "url": "https://ollama.com/library/codeup",
        "tags": [
                [
                        "latest",
                        "7.4 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "DeepSE",
        "categories": [
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Great code generation model based on Llama2."),
    },
    "everythinglm": {
        "url": "https://ollama.com/library/everythinglm",
        "tags": [
                [
                        "latest",
                        "7.4 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Totally Not An LLM",
        "categories": [
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("Uncensored Llama2 based model with support for a 16K context window."),
    },
    "granite3-dense": {
        "url": "https://ollama.com/library/granite3-dense",
        "tags": [
                [
                        "latest",
                        "1.6 GB"
                ],
                [
                        "2b",
                        "1.6 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ]
        ],
        "author": "IBM Research",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "code",
                "multilingual"
        ],
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
        "description": _("The IBM Granite 2B and 8B models are designed to support tool-based use cases and support for retrieval augmented generation (RAG), streamlining code generation, translation and bug fixing."),
    },
    "magicoder": {
        "url": "https://ollama.com/library/magicoder",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ]
        ],
        "author": "iSE",
        "categories": [
                "small",
                "medium",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("🎩 Magicoder is a family of 7B parameter models trained on 75K synthetic instruction data using OSS-Instruct, a novel approach to enlightening LLMs with open-source code snippets."),
    },
    "stablelm-zephyr": {
        "url": "https://ollama.com/library/stablelm-zephyr",
        "tags": [
                [
                        "latest",
                        "1.6 GB"
                ],
                [
                        "3b",
                        "1.6 GB"
                ]
        ],
        "author": "Stability AI",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A lightweight chat model allowing accurate, and responsive output without requiring high-end hardware."),
    },
    "codebooga": {
        "url": "https://ollama.com/library/codebooga",
        "tags": [
                [
                        "latest",
                        "19 GB"
                ],
                [
                        "34b",
                        "19 GB"
                ]
        ],
        "author": "Oobabooga",
        "categories": [
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("A high-performing code instruct model created by merging two existing code models."),
    },
    "falcon2": {
        "url": "https://ollama.com/library/falcon2",
        "tags": [
                [
                        "latest",
                        "6.4 GB"
                ],
                [
                        "11b",
                        "6.4 GB"
                ]
        ],
        "author": "Technology Innovation Institute",
        "categories": [
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Falcon2 is an 11B parameters causal decoder-only model built by TII and trained over 5T tokens."),
    },
    "wizard-vicuna": {
        "url": "https://ollama.com/library/wizard-vicuna",
        "tags": [
                [
                        "latest",
                        "7.4 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "MelodysDreamj",
        "categories": [
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("Wizard Vicuna is a 13B parameter model based on Llama 2 trained by MelodysDreamj."),
    },
    "mistrallite": {
        "url": "https://ollama.com/library/mistrallite",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Amazon Web Services",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("MistralLite is a fine-tuned model based on Mistral with enhanced capabilities of processing long contexts."),
    },
    "mathstral": {
        "url": "https://ollama.com/library/mathstral",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Mistral AI",
        "categories": [
                "small",
                "medium",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("MathΣtral: a 7B model designed for math reasoning and scientific discovery by Mistral AI."),
    },
    "duckdb-nsql": {
        "url": "https://ollama.com/library/duckdb-nsql",
        "tags": [
                [
                        "latest",
                        "3.8 GB"
                ],
                [
                        "7b",
                        "3.8 GB"
                ]
        ],
        "author": "MotherDuck, Numbers Station",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("7B parameter text-to-SQL model made by MotherDuck and Numbers Station."),
    },
    "megadolphin": {
        "url": "https://ollama.com/library/megadolphin",
        "tags": [
                [
                        "latest",
                        "68 GB"
                ],
                [
                        "120b",
                        "68 GB"
                ]
        ],
        "author": "Cognitive Computations",
        "categories": [
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("MegaDolphin-2.2-120b is a transformation of Dolphin-2.2-70b created by interleaving the model with itself."),
    },
    "solar-pro": {
        "url": "https://ollama.com/library/solar-pro",
        "tags": [
                [
                        "latest",
                        "13 GB"
                ],
                [
                        "22b",
                        "13 GB"
                ]
        ],
        "author": "Upstage",
        "categories": [
                "big",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("Solar Pro Preview: an advanced large language model (LLM) with 22 billion parameters designed to fit into a single GPU"),
    },
    "reader-lm": {
        "url": "https://ollama.com/library/reader-lm",
        "tags": [
                [
                        "latest",
                        "935 MB"
                ],
                [
                        "0.5b",
                        "352 MB"
                ],
                [
                        "1.5b",
                        "935 MB"
                ]
        ],
        "author": "JinaAI",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "languages": [
                "en"
        ],
        "description": _("A series of models that convert HTML content to Markdown content, which is useful for content conversion tasks."),
    },
    "notux": {
        "url": "https://ollama.com/library/notux",
        "tags": [
                [
                        "latest",
                        "26 GB"
                ],
                [
                        "8x7b",
                        "26 GB"
                ]
        ],
        "author": "Argilla",
        "categories": [
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A top-performing mixture of experts model, fine-tuned with high-quality data."),
    },
    "notus": {
        "url": "https://ollama.com/library/notus",
        "tags": [
                [
                        "latest",
                        "4.1 GB"
                ],
                [
                        "7b",
                        "4.1 GB"
                ]
        ],
        "author": "Argilla",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A 7B chat model fine-tuned with high-quality data and based on Zephyr."),
    },
    "open-orca-platypus2": {
        "url": "https://ollama.com/library/open-orca-platypus2",
        "tags": [
                [
                        "latest",
                        "7.4 GB"
                ],
                [
                        "13b",
                        "7.4 GB"
                ]
        ],
        "author": "Open Orca",
        "categories": [
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Merge of the Open Orca OpenChat model and the Garage-bAInd Platypus 2 model. Designed for chat and code generation."),
    },
    "goliath": {
        "url": "https://ollama.com/library/goliath",
        "tags": [
                [
                        "latest",
                        "66 GB"
                ]
        ],
        "author": "Alpindale",
        "categories": [
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A language model created by combining two fine-tuned Llama 2 70B models into one."),
    },
    "granite3-moe": {
        "url": "https://ollama.com/library/granite3-moe",
        "tags": [
                [
                        "latest",
                        "822 MB"
                ],
                [
                        "1b",
                        "822 MB"
                ],
                [
                        "3b",
                        "2.1 GB"
                ]
        ],
        "author": "IBM Research",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "multilingual",
                "code"
        ],
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
        "description": _("The IBM Granite 1B and 3B models are the first mixture of experts (MoE) Granite models from IBM designed for low latency usage."),
    },
    "nuextract": {
        "url": "https://ollama.com/library/nuextract",
        "tags": [
                [
                        "latest",
                        "2.2 GB"
                ],
                [
                        "3.8b",
                        "2.2 GB"
                ]
        ],
        "author": "Numind",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A 3.8B model fine-tuned on a private high-quality synthetic dataset for information extraction, based on Phi-3."),
    },
    "aya-expanse": {
        "url": "https://ollama.com/library/aya-expanse",
        "tags": [
                [
                        "latest",
                        "5.1 GB"
                ],
                [
                        "8b",
                        "5.1 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ]
        ],
        "author": "Cohere For AI",
        "categories": [
                "tools",
                "medium",
                "big",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en",
                "ar",
                "zh",
                "cs",
                "nl",
                "fr",
                "de",
                "el",
                "he",
                "hi",
                "id",
                "it",
                "ja",
                "ko",
                "fa",
                "pl",
                "pt",
                "ro",
                "ru",
                "es",
                "tr",
                "uk",
                "vi"
        ],
        "description": _("Cohere For AI's language models trained to perform well across 23 different languages."),
    },
    "dbrx": {
        "url": "https://ollama.com/library/dbrx",
        "tags": [
                [
                        "latest",
                        "74 GB"
                ],
                [
                        "132b",
                        "74 GB"
                ]
        ],
        "author": "Databricks",
        "categories": [
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("DBRX is an open, general-purpose LLM created by Databricks."),
    },
    "marco-o1": {
        "url": "https://ollama.com/library/marco-o1",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ]
        ],
        "author": "AIDC-AI",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("An open large reasoning model for real-world solutions by the Alibaba International Digital Commerce Group (AIDC-AI)."),
    },
    "bge-large": {
        "url": "https://ollama.com/library/bge-large",
        "tags": [
                [
                        "latest",
                        "671 MB"
                ],
                [
                        "335m",
                        "671 MB"
                ]
        ],
        "author": "BGE Large Team",
        "categories": [
                "small",
                "medium",
                "embedding"
        ],
        "languages": [
                "en"
        ],
        "description": _("Embedding model from BAAI mapping texts to vectors."),
    },
    "firefunction-v2": {
        "url": "https://ollama.com/library/firefunction-v2",
        "tags": [
                [
                        "latest",
                        "40 GB"
                ],
                [
                        "70b",
                        "40 GB"
                ]
        ],
        "author": "Fireworks AI",
        "categories": [
                "tools",
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("An open weights function calling model based on Llama 3, competitive with GPT-4o function calling capabilities."),
    },
    "alfred": {
        "url": "https://ollama.com/library/alfred",
        "tags": [
                [
                        "latest",
                        "24 GB"
                ],
                [
                        "40b",
                        "24 GB"
                ]
        ],
        "author": "LightOn AI",
        "categories": [
                "huge"
        ],
        "languages": [
                "en"
        ],
        "description": _("A robust conversational model designed to be used for both chat and instruct use cases."),
    },
    "deepseek-v2.5": {
        "url": "https://ollama.com/library/deepseek-v2.5",
        "tags": [
                [
                        "latest",
                        "133 GB"
                ],
                [
                        "236b",
                        "133 GB"
                ]
        ],
        "author": "DeepSeek Team",
        "categories": [
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("An upgraded version of DeekSeek-V2 that integrates the general and coding abilities of both DeepSeek-V2-Chat and DeepSeek-Coder-V2-Instruct."),
    },
    "shieldgemma": {
        "url": "https://ollama.com/library/shieldgemma",
        "tags": [
                [
                        "latest",
                        "5.8 GB"
                ],
                [
                        "2b",
                        "1.7 GB"
                ],
                [
                        "9b",
                        "5.8 GB"
                ],
                [
                        "27b",
                        "17 GB"
                ]
        ],
        "author": "Google DeepMind",
        "categories": [
                "medium",
                "small",
                "big",
                "huge",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("ShieldGemma is set of instruction tuned models for evaluating the safety of text prompt input and text output responses against a set of defined safety policies."),
    },
    "bespoke-minicheck": {
        "url": "https://ollama.com/library/bespoke-minicheck",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ]
        ],
        "author": "Bespoke Labs",
        "categories": [
                "small",
                "medium"
        ],
        "languages": [
                "en"
        ],
        "description": _("A state-of-the-art fact-checking model developed by Bespoke Labs."),
    },
    "llama-guard3": {
        "url": "https://ollama.com/library/llama-guard3",
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "1b",
                        "1.6 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ]
        ],
        "author": "Meta",
        "categories": [
                "small",
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("Llama Guard 3 is a series of models fine-tuned for content safety classification of LLM inputs and responses."),
    },
    "paraphrase-multilingual": {
        "url": "https://ollama.com/library/paraphrase-multilingual",
        "tags": [
                [
                        "latest",
                        "563 MB"
                ],
                [
                        "278m",
                        "563 MB"
                ]
        ],
        "author": "Paraphrase Team",
        "categories": [
                "small",
                "medium",
                "multilingual",
                "embedding"
        ],
        "languages": [
                "en"
        ],
        "description": _("Sentence-transformers model that can be used for tasks like clustering or semantic search."),
    },
    "opencoder": {
        "url": "https://ollama.com/library/opencoder",
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "1.5b",
                        "1.4 GB"
                ],
                [
                        "8b",
                        "4.7 GB"
                ]
        ],
        "author": "Infly AI",
        "categories": [
                "small",
                "medium",
                "big",
                "code",
                "multilingual"
        ],
        "languages": [
                "en",
                "zh"
        ],
        "description": _("OpenCoder is an open and reproducible code LLM family which includes 1.5B and 8B models, supporting chat in English and Chinese languages."),
    },
    "tulu3": {
        "url": "https://ollama.com/library/tulu3",
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ]
        ],
        "author": "The Allen Institute for AI",
        "categories": [
                "small",
                "medium",
                "huge",
                "code",
                "math"
        ],
        "languages": [
                "en"
        ],
        "description": _("Tülu 3 is a leading instruction following model family, offering fully open-source data, code, and recipes by the The Allen Institute for AI."),
    },
    "snowflake-arctic-embed2": {
        "url": "https://ollama.com/library/snowflake-arctic-embed2",
        "tags": [
                [
                        "latest",
                        "1.2 GB"
                ],
                [
                        "568m",
                        "1.2 GB"
                ]
        ],
        "author": "Snowflake Team",
        "categories": [
                "small",
                "medium",
                "embedding",
                "multilingual"
        ],
        "languages": [
                "en",
                "fr",
                "es",
                "it",
                "de"
        ],
        "description": _("Snowflake's frontier embedding model. Arctic Embed 2.0 adds multilingual support without sacrificing English performance or scalability."),
    },
    "granite3-guardian": {
        "url": "https://ollama.com/library/granite3-guardian",
        "tags": [
                [
                        "latest",
                        "2.7 GB"
                ],
                [
                        "2b",
                        "2.7 GB"
                ],
                [
                        "8b",
                        "5.8 GB"
                ]
        ],
        "author": "IBM Research",
        "categories": [
                "small",
                "medium",
                "big",
                "code"
        ],
        "languages": [
                "en"
        ],
        "description": _("The IBM Granite Guardian 3.0 2B and 8B models are designed to detect risks in prompts and/or responses."),
    },
    "exaone3.5": {
        "url": "https://ollama.com/library/exaone3.5",
        "tags": [
                [
                        "latest",
                        "4.8 GB"
                ],
                [
                        "2.4b",
                        "1.6 GB"
                ],
                [
                        "7.8b",
                        "4.8 GB"
                ],
                [
                        "32b",
                        "19 GB"
                ]
        ],
        "author": "LG AI Research",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "multilingual"
        ],
        "languages": [
                "en",
                "ko"
        ],
        "description": _("EXAONE 3.5 is a collection of instruction-tuned bilingual (English and Korean) generative models ranging from 2.4B to 32B parameters, developed and released by LG AI Research."),
    },
    "sailor2": {
        "url": "https://ollama.com/library/sailor2",
        "tags": [
                [
                        "latest",
                        "5.2 GB"
                ],
                [
                        "1b",
                        "1.1 GB"
                ],
                [
                        "8b",
                        "5.2 GB"
                ],
                [
                        "20b",
                        "12 GB"
                ]
        ],
        "author": "Sailor2 Community",
        "categories": [
                "medium",
                "small",
                "big",
                "huge",
                "multilingual",
                "code"
        ],
        "languages": [
                "en",
                "zh",
                "my",
                "ceb",
                "ilo",
                "id",
                "jv",
                "km",
                "lo",
                "ms",
                "su",
                "tl",
                "th",
                "vi",
                "war"
        ],
        "description": _("Sailor2 are multilingual language models made for South-East Asia. Available in 1B, 8B, and 20B parameter sizes."),
    },
    "falcon3": {
        "tags": [
                [
                        "latest",
                        "4.6 GB"
                ],
                [
                        "1b",
                        "1.8 GB"
                ],
                [
                        "3b",
                        "2.0 GB"
                ],
                [
                        "7b",
                        "4.6 GB"
                ],
                [
                        "10b",
                        "6.3 GB"
                ]
        ],
        "url": "https://ollama.com/library/falcon3",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code",
                "math"
        ],
        "author": "Technology Innovation Institute",
        "languages": [
                "en"
        ],
        "description": _("A family of efficient AI models under 10B parameters performant in science, math, and coding through innovative training techniques."),
    },
    "granite3.1-dense": {
        "tags": [
                [
                        "latest",
                        "5.0 GB"
                ],
                [
                        "2b",
                        "1.6 GB"
                ],
                [
                        "8b",
                        "5.0 GB"
                ]
        ],
        "url": "https://ollama.com/library/granite3.1-dense",
        "categories": [
                "tools",
                "medium",
                "small",
                "big",
                "code",
                "multilingual"
        ],
        "author": "IBM Research",
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
        "description": _("The IBM Granite 2B and 8B models are text-only dense LLMs trained on over 12 trillion tokens of data, demonstrated significant improvements over their predecessors in performance and speed in IBM’s initial testing."),
    },
    "granite3.1-moe": {
        "tags": [
                [
                        "latest",
                        "2.0 GB"
                ],
                [
                        "1b",
                        "1.4 GB"
                ],
                [
                        "3b",
                        "2.0 GB"
                ]
        ],
        "url": "https://ollama.com/library/granite3.1-moe",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "multilingual",
                "code"
        ],
        "author": "IBM Research",
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
        "description": _("The IBM Granite 1B and 3B models are long-context mixture of experts (MoE) Granite models from IBM designed for low latency usage."),
    },
    "granite-embedding": {
        "tags": [
                [
                        "latest",
                        "63 MB"
                ],
                [
                        "30m",
                        "63 MB"
                ],
                [
                        "278m",
                        "563 MB"
                ]
        ],
        "url": "https://ollama.com/library/granite-embedding",
        "categories": [
                "small",
                "medium",
                "big",
                "embedding",
                "code",
                "multilingual"
        ],
        "author": "IBM Research",
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
        "description": _("The IBM Granite Embedding 30M and 278M models models are text-only dense biencoder embedding models, with 30M available in English only and 278M serving multilingual use cases."),
    },
    "phi4": {
        "tags": [
                [
                        "latest",
                        "9.1 GB"
                ],
                [
                        "14b",
                        "9.1 GB"
                ]
        ],
        "url": "https://ollama.com/library/phi4",
        "categories": [
                "medium",
                "big"
        ],
        "author": "Microsoft",
        "languages": [
                "en"
        ],
        "description": _("Phi-4 is a 14B parameter, state-of-the-art open model from Microsoft."),
    },
    "smallthinker": {
        "tags": [
                [
                        "latest",
                        "3.6 GB"
                ],
                [
                        "3b",
                        "3.6 GB"
                ]
        ],
        "url": "https://ollama.com/library/smallthinker",
        "categories": [
                "small",
                "medium"
        ],
        "author": "Power Infer",
        "languages": [
                "en"
        ],
        "description": _("A new small reasoning model fine-tuned from the Qwen 2.5 3B Instruct model."),
    },
    "dolphin3": {
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ]
        ],
        "url": "https://ollama.com/library/dolphin3",
        "categories": [
                "small",
                "medium",
                "code",
                "math"
        ],
        "author": "Cognitive Computations",
        "languages": [
                "en"
        ],
        "description": _("Dolphin 3.0 Llama 3.1 8B 🐬 is the next generation of the Dolphin series of instruct-tuned models designed to be the ultimate general purpose local model, enabling coding, math, agentic, function calling, and general use cases."),
    },
    "deepseek-r1": {
        "tags": [
                [
                        "latest",
                        "5.2 GB"
                ],
                [
                        "1.5b",
                        "1.1 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ],
                [
                        "8b",
                        "5.2 GB"
                ],
                [
                        "14b",
                        "9.0 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ],
                [
                        "671b",
                        "404 GB"
                ]
        ],
        "url": "https://ollama.com/library/deepseek-r1",
        "categories": [
                "tools",
                "medium",
                "small",
                "big",
                "huge",
                "math"
        ],
        "author": "DeepSeek Team",
        "languages": [
                "en"
        ],
        "description": _("DeepSeek-R1 is a family of open reasoning models with performance approaching that of leading models, such as O3 and Gemini 2.5 Pro."),
    },
    "deepseek-v3": {
        "tags": [
                [
                        "latest",
                        "404 GB"
                ],
                [
                        "671b",
                        "404 GB"
                ]
        ],
        "url": "https://ollama.com/library/deepseek-v3",
        "categories": [
                "huge"
        ],
        "author": "DeepSeek Team",
        "languages": [
                "en"
        ],
        "description": _("A strong Mixture-of-Experts (MoE) language model with 671B total parameters with 37B activated for each token."),
    },
    "olmo2": {
        "tags": [
                [
                        "latest",
                        "4.5 GB"
                ],
                [
                        "7b",
                        "4.5 GB"
                ],
                [
                        "13b",
                        "8.4 GB"
                ]
        ],
        "url": "https://ollama.com/library/olmo2",
        "categories": [
                "small",
                "medium",
                "big"
        ],
        "author": "Ai2",
        "languages": [
                "en"
        ],
        "description": _("OLMo 2 is a new family of 7B and 13B models trained on up to 5T tokens. These models are on par with or better than equivalently sized fully open models, and competitive with open-weight models such as Llama 3.1 on English academic benchmarks."),
    },
    "command-r7b": {
        "tags": [
                [
                        "latest",
                        "5.1 GB"
                ],
                [
                        "7b",
                        "5.1 GB"
                ]
        ],
        "url": "https://ollama.com/library/command-r7b",
        "categories": [
                "tools",
                "medium",
                "big",
                "code",
                "multilingual",
                "embedding"
        ],
        "author": "Cohere",
        "languages": [
                "en",
                "fr",
                "es",
                "it",
                "de",
                "pt",
                "ja",
                "ko",
                "ar",
                "zh",
                "ru",
                "pl",
                "tr",
                "vi",
                "nl",
                "cs",
                "id",
                "uk",
                "ro",
                "el",
                "hi",
                "he",
                "fa"
        ],
        "description": _("The smallest model in Cohere's R series delivers top-tier speed, efficiency, and quality to build powerful AI applications on commodity GPUs and edge devices."),
    },
    "openthinker": {
        "tags": [
                [
                        "latest",
                        "4.7 GB"
                ],
                [
                        "7b",
                        "4.7 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ]
        ],
        "url": "https://ollama.com/library/openthinker",
        "categories": [
                "small",
                "medium",
                "huge"
        ],
        "author": "Open Thoughts Team",
        "languages": [
                "en"
        ],
        "description": _("A fully open-source family of reasoning models built using a dataset derived by distilling DeepSeek-R1."),
    },
    "deepscaler": {
        "tags": [
                [
                        "latest",
                        "3.6 GB"
                ],
                [
                        "1.5b",
                        "3.6 GB"
                ]
        ],
        "url": "https://ollama.com/library/deepscaler",
        "categories": [
                "small",
                "medium",
                "math"
        ],
        "author": "Agentica Project",
        "languages": [
                "en"
        ],
        "description": _("A fine-tuned version of Deepseek-R1-Distilled-Qwen-1.5B that surpasses the performance of OpenAI’s o1-preview with just 1.5B parameters on popular math evaluations."),
    },
    "r1-1776": {
        "tags": [
                [
                        "latest",
                        "43 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ],
                [
                        "671b",
                        "404 GB"
                ]
        ],
        "url": "https://ollama.com/library/r1-1776",
        "categories": [
                "huge",
                "multilingual",
                "math"
        ],
        "author": "Perplexity AI",
        "languages": [
                "en",
                "zh",
                "ja"
        ],
        "description": _("A version of the DeepSeek-R1 model that has been post trained to provide unbiased, accurate, and factual information by Perplexity."),
    },
    "gemma3": {
        "tags": [
                [
                        "latest",
                        "3.3 GB"
                ],
                [
                        "270m",
                        "292 MB"
                ],
                [
                        "1b",
                        "815 MB"
                ],
                [
                        "4b",
                        "3.3 GB"
                ],
                [
                        "12b",
                        "8.1 GB"
                ],
                [
                        "27b",
                        "17 GB"
                ]
        ],
        "url": "https://ollama.com/library/gemma3",
        "categories": [
                "vision",
                "small",
                "medium",
                "big",
                "huge"
        ],
        "author": "Google DeepMind",
        "languages": [
                "en"
        ],
        "description": _("The current, most capable model that runs on a single GPU."),
    },
    "phi4-mini": {
        "tags": [
                [
                        "latest",
                        "2.5 GB"
                ],
                [
                        "3.8b",
                        "2.5 GB"
                ]
        ],
        "url": "https://ollama.com/library/phi4-mini",
        "categories": [
                "tools",
                "small",
                "medium",
                "math",
                "multilingual"
        ],
        "author": "Microsoft",
        "languages": [
                "en",
                "ar",
                "zh",
                "cs",
                "da",
                "nl",
                "fi",
                "fr",
                "de",
                "he",
                "hu",
                "it",
                "ja",
                "ko",
                "no",
                "pl",
                "pt",
                "ru",
                "es",
                "sv",
                "th",
                "tr",
                "uk"
        ],
        "description": _("Phi-4-mini brings significant enhancements in multilingual support, reasoning, and mathematics, and now, the long-awaited function calling feature is finally supported."),
    },
    "granite3.2-vision": {
        "tags": [
                [
                        "latest",
                        "2.4 GB"
                ],
                [
                        "2b",
                        "2.4 GB"
                ]
        ],
        "url": "https://ollama.com/library/granite3.2-vision",
        "categories": [
                "vision",
                "tools",
                "small",
                "medium"
        ],
        "author": "IBM for Code Intelligence",
        "languages": [
                "en"
        ],
        "description": _("A compact and efficient vision-language model, specifically designed for visual document understanding, enabling automated content extraction from tables, charts, infographics, plots, diagrams, and more."),
    },
    "granite3.2": {
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "2b",
                        "1.5 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ]
        ],
        "url": "https://ollama.com/library/granite3.2",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "multilingual"
        ],
        "author": "IBM for Code Intelligence",
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
        "description": _("Granite-3.2 is a family of long-context AI models from IBM Granite fine-tuned for thinking capabilities."),
    },
    "command-r7b-arabic": {
        "tags": [
                [
                        "latest",
                        "5.1 GB"
                ],
                [
                        "7b",
                        "5.1 GB"
                ]
        ],
        "url": "https://ollama.com/library/command-r7b-arabic",
        "categories": [
                "tools",
                "medium",
                "big"
        ],
        "author": "Cohere",
        "languages": [
                "en",
                "ar"
        ],
        "description": _("A new state-of-the-art version of the lightweight Command R7B model that excels in advanced Arabic language capabilities for enterprises in the Middle East and Northern Africa."),
    },
    "command-a": {
        "tags": [
                [
                        "latest",
                        "67 GB"
                ],
                [
                        "111b",
                        "67 GB"
                ]
        ],
        "url": "https://ollama.com/library/command-a",
        "categories": [
                "tools",
                "huge",
                "multilingual",
                "code"
        ],
        "author": "Command A Team",
        "languages": [
                "en",
                "fr",
                "es",
                "it",
                "de",
                "pt",
                "ja",
                "ko",
                "ar",
                "zh",
                "ru",
                "pl",
                "tr",
                "vi",
                "nl",
                "cs",
                "id",
                "uk",
                "ro",
                "el",
                "hi",
                "he",
                "fa"
        ],
        "description": _("111 billion parameter model optimized for demanding enterprises that require fast, secure, and high-quality AI"),
    },
    "qwen3": {
        "tags": [
                [
                        "latest",
                        "5.2 GB"
                ],
                [
                        "0.6b",
                        "523 MB"
                ],
                [
                        "1.7b",
                        "1.4 GB"
                ],
                [
                        "4b",
                        "2.5 GB"
                ],
                [
                        "8b",
                        "5.2 GB"
                ],
                [
                        "14b",
                        "9.3 GB"
                ],
                [
                        "30b",
                        "19 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ],
                [
                        "235b",
                        "142 GB"
                ]
        ],
        "description": _("Qwen3 is the latest generation of large language models in Qwen series, offering a comprehensive suite of dense and mixture-of-experts (MoE) models."),
        "url": "https://ollama.com/library/qwen3",
        "categories": [
                "tools",
                "medium",
                "small",
                "big",
                "huge",
                "code",
                "math",
                "multilingual"
        ],
        "author": "Alibaba",
        "languages": [
                "en",
                "fr",
                "pt",
                "de",
                "ro",
                "sv",
                "da",
                "bg",
                "ru",
                "cs",
                "el",
                "uk",
                "es",
                "nl",
                "sk",
                "hr",
                "pl",
                "lt",
                "nb",
                "nn",
                "fa",
                "sl",
                "gu",
                "lv",
                "it",
                "oc",
                "ne",
                "mr",
                "be",
                "sr",
                "lb",
                "vec",
                "as",
                "cy",
                "szl",
                "ast",
                "hne",
                "awa",
                "mai",
                "bho",
                "sd",
                "ga",
                "fo",
                "hi",
                "pa",
                "bn",
                "or",
                "tg",
                "yi",
                "lmo",
                "lij",
                "sc",
                "fur",
                "scn",
                "gl",
                "ca",
                "is",
                "sq",
                "li",
                "prs",
                "af",
                "mk",
                "si",
                "ur",
                "mag",
                "bs",
                "hy",
                "zh-hans",
                "zh-hant",
                "yue",
                "my",
                "ar",
                "ar-naj",
                "ar-lev",
                "ar-eg",
                "ar-ma",
                "ar-iq",
                "ar-ye",
                "ar-tn",
                "he",
                "mt",
                "id",
                "ms",
                "tl",
                "ceb",
                "jv",
                "su",
                "min",
                "ban",
                "bjn",
                "pag",
                "ilo",
                "war",
                "ta",
                "te",
                "kn",
                "ml",
                "tr",
                "az",
                "uz",
                "kk",
                "ba",
                "tt",
                "th",
                "lo",
                "fi",
                "et",
                "hu",
                "vi",
                "km",
                "ja",
                "ko",
                "ka",
                "eu",
                "ht",
                "pap",
                "kea",
                "tpi",
                "sw"
        ],
    },
    "devstral": {
        "tags": [
                [
                        "latest",
                        "14 GB"
                ],
                [
                        "24b",
                        "14 GB"
                ]
        ],
        "description": _("Devstral: the best open source model for coding agents"),
        "url": "https://ollama.com/library/devstral",
        "categories": [
                "tools",
                "big",
                "huge",
                "code"
        ],
        "author": "Mistral AI",
        "languages": [
                "en"
        ],
    },
    "llama4": {
        "tags": [
                [
                        "latest",
                        "67 GB"
                ],
                [
                        "16x17b",
                        "67 GB"
                ],
                [
                        "128x17b",
                        "245 GB"
                ]
        ],
        "description": _("Meta's latest collection of multimodal models."),
        "url": "https://ollama.com/library/llama4",
        "categories": [
                "vision",
                "tools",
                "huge",
                "multilingual",
                "code"
        ],
        "author": "Meta",
        "languages": [
                "en",
                "ar",
                "fr",
                "de",
                "hi",
                "id",
                "it",
                "pt",
                "es",
                "tl",
                "th",
                "vi"
        ],
    },
    "qwen2.5vl": {
        "tags": [
                [
                        "latest",
                        "6.0 GB"
                ],
                [
                        "3b",
                        "3.2 GB"
                ],
                [
                        "7b",
                        "6.0 GB"
                ],
                [
                        "32b",
                        "21 GB"
                ],
                [
                        "72b",
                        "49 GB"
                ]
        ],
        "description": _("Flagship vision-language model of Qwen and also a significant leap from the previous Qwen2-VL."),
        "url": "https://ollama.com/library/qwen2.5vl",
        "categories": [
                "vision",
                "medium",
                "small",
                "big",
                "huge",
                "math"
        ],
        "author": "Alibaba",
        "languages": [
                "en"
        ],
    },
    "deepcoder": {
        "tags": [
                [
                        "latest",
                        "9.0 GB"
                ],
                [
                        "1.5b",
                        "1.1 GB"
                ],
                [
                        "14b",
                        "9.0 GB"
                ]
        ],
        "description": _("DeepCoder is a fully open-Source 14B coder model at O3-mini level, with a 1.5B version also available."),
        "url": "https://ollama.com/library/deepcoder",
        "categories": [
                "medium",
                "small",
                "big",
                "code"
        ],
        "author": "Agentica and Together AI",
        "languages": [
                "en"
        ],
    },
    "mistral-small3.1": {
        "tags": [
                [
                        "latest",
                        "15 GB"
                ],
                [
                        "24b",
                        "15 GB"
                ]
        ],
        "description": _("Building upon Mistral Small 3, Mistral Small 3.1 (2503) adds state-of-the-art vision understanding and enhances long context capabilities up to 128k tokens without compromising text performance."),
        "url": "https://ollama.com/library/mistral-small3.1",
        "categories": [
                "vision",
                "tools",
                "big",
                "huge"
        ],
        "author": "Mistral AI",
        "languages": [
                "en"
        ],
    },
    "cogito": {
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "3b",
                        "2.2 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ],
                [
                        "14b",
                        "9.0 GB"
                ],
                [
                        "32b",
                        "20 GB"
                ],
                [
                        "70b",
                        "43 GB"
                ]
        ],
        "description": _("Cogito v1 Preview is a family of hybrid reasoning models by Deep Cogito that outperform the best available open models of the same size, including counterparts from LLaMA, DeepSeek, and Qwen across most standard benchmarks."),
        "url": "https://ollama.com/library/cogito",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "huge"
        ],
        "author": "Deep Cogito",
        "languages": [
                "en"
        ],
    },
    "granite3.3": {
        "tags": [
                [
                        "latest",
                        "4.9 GB"
                ],
                [
                        "2b",
                        "1.5 GB"
                ],
                [
                        "8b",
                        "4.9 GB"
                ]
        ],
        "description": _("IBM Granite 2B and 8B models are 128K context length language models that have been fine-tuned for improved reasoning and instruction-following capabilities."),
        "url": "https://ollama.com/library/granite3.3",
        "categories": [
                "tools",
                "small",
                "medium",
                "big",
                "code",
                "math",
                "multilingual"
        ],
        "author": "IBM Research",
        "languages": [
                "en",
                "de",
                "es",
                "fr",
                "ja",
                "pt",
                "ar",
                "cs",
                "it",
                "ko",
                "nl",
                "zh"
        ],
    },
    "phi4-reasoning": {
        "tags": [
                [
                        "latest",
                        "11 GB"
                ],
                [
                        "14b",
                        "11 GB"
                ]
        ],
        "description": _("Phi 4 reasoning and reasoning plus are 14-billion parameter open-weight reasoning models that rival much larger models on complex reasoning tasks."),
        "url": "https://ollama.com/library/phi4-reasoning",
        "categories": [
                "big",
                "huge",
                "math",
                "code"
        ],
        "author": "Microsoft",
        "languages": [
                "en"
        ],
    },
    "exaone-deep": {
        "tags": [
                [
                        "latest",
                        "4.8 GB"
                ],
                [
                        "2.4b",
                        "1.6 GB"
                ],
                [
                        "7.8b",
                        "4.8 GB"
                ],
                [
                        "32b",
                        "19 GB"
                ]
        ],
        "description": _("EXAONE Deep exhibits superior capabilities in various reasoning tasks including math and coding benchmarks, ranging from 2.4B to 32B parameters developed and released by LG AI Research."),
        "url": "https://ollama.com/library/exaone-deep",
        "categories": [
                "small",
                "medium",
                "big",
                "huge",
                "code",
                "math"
        ],
        "author": "LG AI Research",
        "languages": [
                "en"
        ],
    },
    "phi4-mini-reasoning": {
        "tags": [
                [
                        "latest",
                        "3.2 GB"
                ],
                [
                        "3.8b",
                        "3.2 GB"
                ]
        ],
        "description": _("Phi 4 mini reasoning is a lightweight open model that balances efficiency with advanced reasoning ability."),
        "url": "https://ollama.com/library/phi4-mini-reasoning",
        "categories": [
                "small",
                "medium",
                "math"
        ],
        "author": "Microsoft",
        "languages": [
                "en"
        ],
    },
    "gemma3n": {
        "tags": [
                [
                        "latest",
                        "7.5 GB"
                ],
                [
                        "e2b",
                        "5.6 GB"
                ],
                [
                        "e4b",
                        "7.5 GB"
                ]
        ],
        "description": _("Gemma 3n models are designed for efficient execution on everyday devices such as laptops, tablets or phones."),
        "url": "https://ollama.com/library/gemma3n",
        "categories": [
                "medium",
                "big",
                "huge"
        ],
        "author": "Google DeepMind",
        "languages": [
                "en"
        ],
    },
    "magistral": {
        "tags": [
                [
                        "latest",
                        "14 GB"
                ],
                [
                        "24b",
                        "14 GB"
                ]
        ],
        "description": _("Magistral is a small, efficient reasoning model with 24B parameters."),
        "url": "https://ollama.com/library/magistral",
        "categories": [
                "tools",
                "big",
                "huge",
                "multilingual",
                "code"
        ],
        "author": "Mistral AI",
        "languages": [
                "en",
                "ar",
                "zh",
                "cs",
                "da",
                "nl",
                "fi",
                "fr",
                "de",
                "he",
                "hu",
                "it",
                "ja",
                "ko",
                "no",
                "pl",
                "pt",
                "ru",
                "es",
                "sv",
                "th",
                "tr",
                "uk"
        ],
    },
    "mistral-small3.2": {
        "tags": [
                [
                        "latest",
                        "15 GB"
                ],
                [
                        "24b",
                        "15 GB"
                ]
        ],
        "description": _("An update to Mistral Small that improves on function calling, instruction following, and less repetition errors."),
        "url": "https://ollama.com/library/mistral-small3.2",
        "categories": [
                "vision",
                "tools",
                "big",
                "huge"
        ],
        "author": "Mistral AI",
        "languages": [
                "en"
        ],
    },
    "gpt-oss": {
        "tags": [
                [
                        "latest",
                        "14 GB"
                ],
                [
                        "20b",
                        "14 GB"
                ],
                [
                        "120b",
                        "65 GB"
                ]
        ],
        "description": _("OpenAI’s open-weight models designed for powerful reasoning, agentic tasks, and versatile developer use cases."),
        "url": "https://ollama.com/library/gpt-oss",
        "categories": [
                "tools",
                "big",
                "huge"
        ],
        "author": "OpenAI",
        "languages": [
                "en"
        ],
    },
    "qwen3-coder": {
        "tags": [
                [
                        "latest",
                        "19 GB"
                ],
                [
                        "30b",
                        "19 GB"
                ],
                [
                        "480b",
                        "290 GB"
                ]
        ],
        "description": _("Alibaba's performant long context models for agentic and coding tasks."),
        "url": "https://ollama.com/library/qwen3-coder",
        "categories": [
                "big",
                "huge",
                "code"
        ],
        "author": "Alibaba",
        "languages": [
                "en"
        ],
    },
    "embeddinggemma": {
        "tags": [
                [
                        "latest",
                        "622 MB"
                ],
                [
                        "300m",
                        "622 MB"
                ]
        ],
        "description": _("EmbeddingGemma is a 300M parameter embedding model from Google."),
        "url": "https://ollama.com/library/embeddinggemma",
        "categories": [
                "small",
                "medium",
                "embedding",
                "multilingual"
        ],
        "author": "Google DeepMind",
        "languages": [
                "de",
                "fr",
                "es",
                "pt",
                "it",
                "nl",
                "ru",
                "cs",
                "pl",
                "ar",
                "fa",
                "he",
                "tr",
                "ja",
                "ko",
                "vi",
                "th",
                "id",
                "ms",
                "lo",
                "my",
                "ceb",
                "km",
                "tl",
                "hi",
                "bn",
                "ur"
        ],
    },
    "deepseek-v3.1": {
        "tags": [
                [
                        "latest",
                        "404 GB"
                ],
                [
                        "671b",
                        "404 GB"
                ]
        ],
        "description": _("DeepSeek-V3.1 is a hybrid model that supports both thinking mode and non-thinking mode."),
        "url": "https://ollama.com/library/deepseek-v3.1",
        "categories": [
                "tools",
                "huge"
        ],
        "author": "DeepSeek Team",
        "languages": [
                "en"
        ],
    },
}
