<p align="center"><img src="https://jeffser.com/images/alpaca/logo.svg"></p>

# Alpaca

<a href='https://flathub.org/apps/com.jeffser.Alpaca'><img width='240' alt='Download on Flathub' src='https://flathub.org/api/badge?locale=en'/></a>

Alpaca is an [Ollama](https://github.com/ollama/ollama) client where you can manage and chat with multiple models, Alpaca provides an easy and begginer friendly way of interacting with local AI, everything is open source and powered by Ollama.

---

> [!NOTE]
> Please checkout [this discussion](https://github.com/Jeffser/Alpaca/discussions/292), I want to start developing a new app alongside Alpaca but I need some suggestions, thanks!

> [!WARNING]
> This project is not affiliated at all with Ollama, I'm not responsible for any damages to your device or software caused by running code given by any AI models.

> [!IMPORTANT]
> Please be aware that [GNOME Code of Conduct](https://conduct.gnome.org) applies to Alpaca before interacting with this repository.

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
- Website recognition (Ask questions about a certain website by parsing the url)

## Screenies

Normal conversation | Image recognition | Code highlighting | YouTube transcription | Model management
:------------------:|:-----------------:|:-----------------:|:---------------------:|:----------------:
![screenie1](https://jeffser.com/images/alpaca/screenie1.png) | ![screenie2](https://jeffser.com/images/alpaca/screenie2.png) | ![screenie3](https://jeffser.com/images/alpaca/screenie3.png) | ![screenie4](https://jeffser.com/images/alpaca/screenie4.png) | ![screenie5](https://jeffser.com/images/alpaca/screenie5.png)

## Installation

### Flathub

You can find the latest stable version of the app on [Flathub](https://flathub.org/apps/com.jeffser.Alpaca)

### Flatpak Package

Everytime a new version is published they become available on the [releases page](https://github.com/Jeffser/Alpaca/releases) of the repository

### Building Git Version

Note: This is not recommended since the prerelease versions of the app often present errors and general instability.

1. Clone the project
2. Open with Gnome Builder
3. Press the run button (or export if you want to build a Flatpak package)

### System Installation (Arch Linux)

> [!NOTE]
> This method doesn't include the Ollama instance

```BASH
mkdir Alpaca-build
cd Alpaca-build
curl -L -o PKGBUILD https://raw.githubusercontent.com/jeffser/Alpaca/main/PKGBUILD
makepkg -si
```

## Translators

Language               | Contributors
:----------------------|:-----------
🇷🇺 Russian              | [Alex K](https://github.com/alexkdeveloper)
🇪🇸 Spanish              | [Jeffry Samuel](https://github.com/jeffser)
🇫🇷 French               | [Louis Chauvet-Villaret](https://github.com/loulou64490) , [Théo FORTIN](https://github.com/topiga)
🇧🇷 Brazilian Portuguese | [Daimar Stein](https://github.com/not-a-dev-stein)
🇳🇴 Norwegian            | [CounterFlow64](https://github.com/CounterFlow64)
🇮🇳 Bengali              | [Aritra Saha](https://github.com/olumolu)
🇨🇳 Simplified Chinese   | [Yuehao Sui](https://github.com/8ar10der) , [Aleksana](https://github.com/Aleksanaa)
🇮🇳 Hindi                | [Aritra Saha](https://github.com/olumolu)
🇹🇷 Turkish              | [YusaBecerikli](https://github.com/YusaBecerikli)
🇺🇦 Ukrainian            | [Simon](https://github.com/OriginalSimon)
🇩🇪 German               | [Marcel Margenberg](https://github.com/MehrzweckMandala)

Want to add a language? Visit [this discussion](https://github.com/Jeffser/Alpaca/discussions/153) to get started!

---

## Thanks

- [not-a-dev-stein](https://github.com/not-a-dev-stein) for their help with requesting a new icon and bug reports
- [TylerLaBree](https://github.com/TylerLaBree) for their requests and ideas
- [Imbev](https://github.com/imbev) for their reports and suggestions
- [Nokse](https://github.com/Nokse22) for their contributions to the UI and table rendering
- [Louis Chauvet-Villaret](https://github.com/loulou64490) for their suggestions
- [Aleksana](https://github.com/Aleksanaa) for her help with better handling of directories
- Sponsors for giving me enough money to be able to take a ride to my campus every time I need to <3
- Everyone that has shared kind words of encouragement!

---

## Dependencies

- [Requests](https://github.com/psf/requests)
- [Pillow](https://github.com/python-pillow/Pillow)
- [Pypdf](https://github.com/py-pdf/pypdf)
- [Pytube](https://github.com/pytube/pytube)
- [Html2Text](https://github.com/aaronsw/html2text)
- [Ollama](https://github.com/ollama/ollama)
- [Numactl](https://github.com/numactl/numactl)
