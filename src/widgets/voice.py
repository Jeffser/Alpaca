# voice.py
"""
Manages TTS and STT code
"""


import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf
from ..sql_manager import Instance as SQL
from ..constants import data_dir, STT_MODELS, SPEACH_RECOGNITION_LANGUAGES, TTS_VOICES
from . import dialog, model_manager, blocks

import os, threading, importlib.util, re, unicodedata, gc
import numpy as np

message_dictated = None
libraries = {
    'kokoro': None,
    'sounddevice': None,
    'whisper': None,
    'pyaudio': None
}
library_waiting_queue = [] # For every widget that requires the libraries
loaded_whisper_models = {}
tts_engine = None
tts_engine_language = None

def preload_heavy_libraries():
    for library_name in libraries:
        if importlib.util.find_spec(library_name):
            libraries[library_name] = importlib.import_module(library_name)
    for widget in library_waiting_queue:
        widget.set_sensitive(True)

threading.Thread(target=preload_heavy_libraries).start()

class DictateToggleButton(Gtk.Stack):
    __gtype_name__ = 'AlpacaDictateToggleButton'

    def __init__(self, message_element):
        self.message_element = message_element
        super().__init__(
            visible = importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice')
        )
        self.button = Gtk.ToggleButton(
            halign=1,
            hexpand=True,
            icon_name='bullhorn-symbolic',
            css_classes=["flat"],
            tooltip_text=_("Dictate Message")
        )
        self.button.connect('toggled', self.dictate_message)
        self.add_named(self.button, 'button')
        self.add_named(Adw.Spinner(css_classes=['p10']), 'loading')

        if self.get_visible() and (libraries.get('kokoro') is None or libraries.get('sounddevice') is None):
            library_waiting_queue.append(self)
            self.set_sensitive(False)

    def set_active(self, state):
        self.button.set_active(state)

    def get_active(self) -> bool:
        return self.button.get_active()

    def dictate_message(self, button):
        global message_dictated, tts_engine
        if not self.message_element.get_root():
            return
        def run():
            GLib.idle_add(self.set_visible_child_name, 'loading')
            voice = None
            if self.message_element.get_model():
                voice = SQL.get_model_preferences(self.message_element.get_model()).get('voice', None)
            if not voice:
                voice = TTS_VOICES.get(list(TTS_VOICES.keys())[self.message_element.get_root().settings.get_value('tts-model').unpack()])

            if model_manager.tts_model_path:
                if not os.path.islink(os.path.join(model_manager.tts_model_path, '{}.pt'.format(voice))) and self.message_element.get_root().get_name() == 'AlpacaWindow':
                    pretty_name = [k for k, v in TTS_VOICES.items() if v == voice]
                    if len(pretty_name) > 0:
                        pretty_name = pretty_name[0]
                        self.message_element.get_root().local_model_flowbox.append(model_manager.TextToSpeechModel(pretty_name))
            if not tts_engine or tts_engine_language != voice[0]:
                tts_engine = libraries.get('kokoro').KPipeline(lang_code=voice[0], repo_id='hexgrad/Kokoro-82M')
                tts_engine_language=voice[0]
            queue_index = 0
            while queue_index < len(self.message_element.get_content_for_dictation()):
                text = self.message_element.get_content_for_dictation()
                end_index = max(text.rfind("\n"), text.rfind("."), text.rfind("?"), text.rfind("!"), text.rfind(":"))
                if end_index == -1 or end_index < queue_index:
                    end_index = len(text)
                if text[queue_index:end_index]:
                    if self.message_element.get_root().get_name() == 'AlpacaLiveChat':
                        self.message_element.get_root().response_label.set_label(text[queue_index:end_index])
                    try:
                        generator = tts_engine(
                            text[queue_index:end_index],
                            voice=voice,
                            speed=1.2,
                            split_pattern=r'\n+'
                        )
                        for gs, ps, audio in generator:
                            if not button.get_active():
                                return
                            libraries.get('sounddevice').play(audio, samplerate=24000)
                            GLib.idle_add(self.set_visible_child_name, 'button')
                            libraries.get('sounddevice').wait()
                    except Exception as e:
                        dialog.simple_error(
                            parent=self.message_element.get_root(),
                            title=_('Text to Speech Error'),
                            body=_('An error occurred while running text to speech model'),
                            error_log=e,
                        )
                        break
                else:
                    break
                queue_index = end_index
            if generator:
                del generator
            gc.collect()
            GLib.idle_add(self.set_active, False)

        if button.get_active():
            GLib.idle_add(self.message_element.add_css_class, 'tts_message')
            if message_dictated and message_dictated.popup.tts_button.get_active():
                 message_dictated.popup.tts_button.set_active(False)
            message_dictated = self.message_element
            threading.Thread(target=run).start()
        else:
            GLib.idle_add(self.message_element.remove_css_class, 'tts_message')
            GLib.idle_add(self.set_visible_child_name, 'button')
            message_dictated = None
            threading.Thread(target=libraries.get('sounddevice').stop).start()

class MicrophoneButton(Gtk.Stack):
    __gtype_name__ = 'AlpacaMicrophoneButton'

    def __init__(self, text_view):
        self.text_view = text_view

        super().__init__(
            visible = importlib.util.find_spec('whisper')
        )
        self.button = Gtk.ToggleButton(
            icon_name='audio-input-microphone-symbolic',
            tooltip_text=_('Use Speech Recognition'),
            css_classes=['br0']
        )
        self.button.connect('toggled', self.toggled)
        self.add_named(self.button, 'button')
        self.add_named(Adw.Spinner(css_classes=['p10']), 'loading')
        self.mic_timeout = 0

        if self.get_visible() and (libraries.get('whisper') is None or libraries.get('pyaudio') is None):
            library_waiting_queue.append(self)
            self.set_sensitive(False)

    def toggled(self, button):
        global loaded_whisper_models
        language=SPEACH_RECOGNITION_LANGUAGES[self.get_root().settings.get_value('stt-language').unpack()]
        buffer = self.text_view.get_buffer()
        model_name = os.getenv("ALPACA_SPEECH_MODEL", "base")
        p = None
        stream = None

        def recognize_audio(model, audio_data, current_iter):
            result = model.transcribe(audio_data, language=language)
            if len(result.get("text").encode('utf8')) == 0:
                self.mic_timeout += 1
            else:
                GLib.idle_add(buffer.insert, current_iter, result.get("text"), len(result.get("text").encode('utf8')))
                self.mic_timeout = 0

        def run_mic(pulling_model:Gtk.Widget=None):
            GLib.idle_add(button.get_parent().set_visible_child_name, "loading")
            GLib.idle_add(button.add_css_class, 'accent')

            samplerate=16000
            model = None

            self.mic_timeout=0

            try:
                if not loaded_whisper_models.get(model_name):
                    loaded_whisper_models[model_name] = libraries.get('whisper').load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
                if pulling_model:
                    GLib.idle_add(pulling_model.update_progressbar, {'status': 'success'})
            except Exception as e:
                dialog.simple_error(
                    parent = button.get_root(),
                    title = _('Speech Recognition Error'),
                    body = _('An error occurred while pulling speech recognition model'),
                    error_log = e
                )
                logger.error(e)
            GLib.idle_add(button.get_parent().set_visible_child_name, "button")

            if loaded_whisper_models.get(model_name):
                stream = libraries.get('pyaudio').PyAudio().open(
                    format=libraries.get('pyaudio').paInt16,
                    rate=samplerate,
                    input=True,
                    frames_per_buffer=1024,
                    channels=1
                )

                try:
                    mic_auto_send = self.get_root().settings.get_value('stt-auto-send').unpack()
                    while button.get_active():
                        frames = []
                        for i in range(0, int(samplerate / 1024 * 2)):
                            data = stream.read(1024, exception_on_overflow=False)
                            frames.append(np.frombuffer(data, dtype=np.int16))
                        audio_data = np.concatenate(frames).astype(np.float32) / 32768.0
                        threading.Thread(target=recognize_audio, args=(loaded_whisper_models.get(model_name), audio_data, buffer.get_end_iter())).start()

                        if self.mic_timeout >= 2 and mic_auto_send and buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False):
                            GLib.idle_add(button.get_root().send_message)
                            break

                except Exception as e:
                    dialog.simple_error(
                        parent = button.get_root(),
                        title = _('Speech Recognition Error'),
                        body = _('An error occurred while using speech recognition'),
                        error_log = e
                    )
                    logger.error(e)
                finally:
                    stream.stop_stream()
                    stream.close()
                    libraries.get('pyaudio').PyAudio().terminate()
                    if stream:
                        del stream
                    gc.collect()

            if button.get_active():
                button.set_active(False)

        def prepare_download():
            if button.get_root().get_name() == 'AlpacaWindow':
                pulling_model = model_manager.PullingModel(model_name, model_manager.add_speech_to_text_model, False)
                button.get_root().local_model_flowbox.prepend(pulling_model)
            threading.Thread(target=run_mic, args=(pulling_model,)).start()

        if button.get_active():
            if os.path.isfile(os.path.join(data_dir, 'whisper', '{}.pt'.format(model_name))):
                if message_dictated:
                    message_dictated.popup.tts_button.set_active(False)
                threading.Thread(target=run_mic).start()
            else:
                dialog.simple(
                    parent = button.get_root(),
                    heading = _("Download Speech Recognition Model"),
                    body = _("To use speech recognition you'll need to download a special model ({})").format(STT_MODELS.get(model_name, '~151mb')),
                    callback = prepare_download,
                    button_name = _("Download Model")
                )
        else:
            button.remove_css_class('accent')
            button.set_sensitive(False)
            GLib.timeout_add(2000, lambda button: button.set_sensitive(True) and False, button)
