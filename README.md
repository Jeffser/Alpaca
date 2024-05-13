# Alpaca

An [Ollama](https://github.com/ollama/ollama) client made with GTK4 and Adwaita.

## ‼️I NEED AN ICON‼️
I'm not a graphic designer, it would mean the world to me if someone could make a [GNOME icon](https://developer.gnome.org/hig/guidelines/app-icons.html) for this app.

## ⚠️THIS IS UNDER DEVELOPMENT⚠️
This is my first GTK4 / Adwaita / Python app, so it might crash and some features are still under development, please report any errors if you can, thank you!

## Features!
- Talk to multiple models in the same conversation
- Pull and delete models from the app

## Future features!
- Persistent conversations
- Multiple conversations
- Image / document recognition

## Preview
1. Clone repo using Gnome Builder
2. Press the `run` button

## Instalation
1. Clone repo using Gnome Builder
2. Build the app using the `build` button
3. Prepare the file using the `install` button (it doesn't actually install it, idk)
4. Then press the `export` button, it will export a `com.jeffser.Alpaca.flatpak` file, you can install it just by opening it

## Usage
- You'll need an Ollama instance, I recommend using the [Docker image](https://ollama.com/blog/ollama-is-now-available-as-an-official-docker-image)
- Once you open Alpaca it will ask you for a url, if you are using the same computer as the Ollama instance and didn't change the ports you can use the default url.
- You might need a model, you can get one using the box icon at the top of the app, I recommend using phi3 because it is very lightweight but you can use whatever you want (I haven't actually tested all so your mileage may vary).
- Then just start talking! you can mix different models, they all share the same conversation, it's really cool in my opinion.
