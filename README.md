<p align="center"><img src="https://jeffser.com/images/alpaca/logo.svg">
<h1 align="center">Alpaca</h1>

<p align="center">Alpaca is an <a href="https://github.com/ollama/ollama">Ollama</a> client where you can manage and chat with multiple models, Alpaca provides an easy and beginner friendly way of interacting with local AI, everything is open source and powered by Ollama.</p>

<p align="center">You can also use third party AI providers such as Gemini, ChatGPT and more!</p>

<p align="center"><a href='https://flathub.org/apps/com.jeffser.Alpaca'><img width='190' alt='Download on Flathub' src='https://flathub.org/api/badge?locale=en'/></a></p>

---

> [!WARNING]
> This project is not affiliated at all with Ollama, I'm not responsible for any damages to your device or software caused by running code given by any AI models.

> [!IMPORTANT]
> Please be aware that [GNOME Code of Conduct](https://conduct.gnome.org) applies to Alpaca before interacting with this repository.

> [!WARNING]
> AI generated issues and PRs will be denied, repeated offense will result in a ban from the repository, AI can be a useful tool but I don't want Alpaca to be vibe-developed, thanks.

## Features!

- Talk to multiple models in the same conversation
- Pull and delete models from the app
- Image recognition
- Document recognition (plain text files)
- Code highlighting
- Multiple conversations
- Notifications
- Import / Export chats
- Delete / Edit messages
- Regenerate messages
- YouTube recognition (Ask questions about a YouTube video using the transcript)
- Website recognition (Ask questions about a certain website by pasting the URL)
- Talk to cloud-hosted models with OpenAI-compatible APIs using your own API keys

## Screenies

Normal conversation | Image recognition | Custom Character | Integrated Script Execution | Web Search Integration
:------------------:|:-----------------:|:----------------:|:---------------------------:|:--------------------:
![screenie1](https://jeffser.com/images/alpaca/screenie1.png) | ![screenie2](https://jeffser.com/images/alpaca/screenie2.png) | ![screenie3](https://jeffser.com/images/alpaca/screenie3.png) | ![screenie4](https://jeffser.com/images/alpaca/screenie5.png) | ![screenie5](https://jeffser.com/images/alpaca/screenie6.png)

## Installation

- [Alpaca Installation](https://github.com/Jeffser/Alpaca/wiki/Installation)
- [Ollama Installation](https://github.com/Jeffser/Alpaca/wiki/Installing-Ollama)

## Launch in Quick Ask Mode

> [!NOTE]
> Available since Alpaca 6.0.0

> [!NOTE]
> It uses the default model from the latest instance you've used to generate the messages

Quick Ask is a mini mode you can use to have a quick temporary chat that isn't saved as a full chat.

Great for asking something, getting a response and moving on with your work.

```BASH
flatpak run com.jeffser.Alpaca --quick-ask
```

## Launch in Live Chat Mode

> [!NOTE]
> Available since Alpaca 7.0.0

Live Chat is a great way of having a live conversation with your models as if you were in a call with them.

Great for natural conversations with models and roleplay.

```BASH
flatpak run com.jeffser.Alpaca --live-chat
```

You can add your respective command as as keyboard shortcut in your system settings to quickly access Alpaca at anytime!

## Translators

Language                | Contributors
:-----------------------|:-----------
🇷🇺 Russian              | [Alex K](https://github.com/alexkdeveloper) [DasHi](https://github.com/col83)
🇪🇸 Spanish              | [Jeffry Samuel](https://github.com/jeffser)
🇫🇷 French               | [Louis Chauvet-Villaret](https://github.com/loulou64490) , [Théo FORTIN](https://github.com/topiga)
🇧🇷 Brazilian Portuguese | [Daimar Stein](https://github.com/not-a-dev-stein) , [Bruno Antunes](https://github.com/antun3s)
🇳🇴 Norwegian            | [CounterFlow64](https://github.com/CounterFlow64)
🇮🇳 Bengali              | [Aritra Saha](https://github.com/olumolu)
🇨🇳 Simplified Chinese   | [Yuehao Sui](https://github.com/8ar10der) , [Aleksana](https://github.com/Aleksanaa)
🇮🇳 Hindi                | [Aritra Saha](https://github.com/olumolu)
🇹🇷 Turkish              | [YusaBecerikli](https://github.com/YusaBecerikli)
🇺🇦 Ukrainian            | [Simon](https://github.com/OriginalSimon)
🇩🇪 German               | [Marcel Margenberg](https://github.com/MehrzweckMandala)
🇮🇱 Hebrew               | [Yosef Or Boczko](https://github.com/yoseforb)
🇮🇳 Telugu               | [Aryan Karamtoth](https://github.com/SpaciousCoder78)
🇮🇹 Italian              | [Edoardo Brogiolo](https://github.com/edo0)
🇯🇵 Japanese             | [Shidore](https://github.com/sh1d0re)
🇳🇱 Dutch                | [Henk Leerssen](https://github.com/Henkster72)
🇮🇩 Indonesian           | [Nofal Briansah](https://github.com/nofalbriansah)
🌐 Tamil                | [Harimanish](https://github.com/harimanish)
🇬🇪 Georgian             | [Ekaterine Papava](https://github.com/EkaterinePapava)
🇮🇳 Kannada              | [Jeethan Roche](https://github.com/roche-jeethan)
🌐 Arabic               | [Ahmed Najmawi](https://github.com/x9a)
🌐 Belarusian           | [Aliaksandr Kliujeŭ](https://github.com/PlagaMedicum)
🌐 Kabyle               | [Athmane MOKRAOUI](https://github.com/BoFFire) , [MoonShadow](https://github.com/ZiriSut)

Want to add a language? Visit [this discussion](https://github.com/Jeffser/Alpaca/discussions/153) to get started!

---

## Thanks

- [not-a-dev-stein](https://github.com/not-a-dev-stein) for their help with requesting a new icon and bug reports
- [TylerLaBree](https://github.com/TylerLaBree) for their requests and ideas
- [Imbev](https://github.com/imbev) for their reports and suggestions
- [Nokse](https://github.com/Nokse22) for their contributions to the UI and table rendering
- [Louis Chauvet-Villaret](https://github.com/loulou64490) for their suggestions
- [Aleksana](https://github.com/Aleksanaa) for her help with better handling of directories
- [Gnome Builder Team](https://gitlab.gnome.org/GNOME/gnome-builder) for the awesome IDE I use to develop Alpaca
- Sponsors for giving me enough money to be able to take a ride to my campus every time I need to <3
- Everyone that has shared kind words of encouragement!

---

## Packaging Alpaca

If you want to package Alpaca in a different packaging method please read [this wiki page](https://github.com/Jeffser/Alpaca/wiki/Packaging-Alpaca).
