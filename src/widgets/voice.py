# voice.py
"""
Manages TTS and STT code
"""


import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ..sql_manager import Instance as SQL
from ..constants import data_dir, cache_dir, STT_MODELS, SPEACH_RECOGNITION_LANGUAGES, TTS_VOICES
from . import dialog, models, blocks, activities

import os, threading, importlib.util, re, unicodedata, gc, queue, time, logging
import numpy as np

logger = logging.getLogger(__name__)

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
    global library_waiting_queue, libraries
    for library_name in libraries:
        if libraries.get(library_name) is None and importlib.util.find_spec(library_name):
            libraries[library_name] = importlib.import_module(library_name)
    for widget in library_waiting_queue:
        widget.set_sensitive(True)
    library_waiting_queue = []

threading.Thread(target=preload_heavy_libraries, daemon=True).start()

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
        self.play_queue = queue.Queue()

        if self.get_visible() and (libraries.get('kokoro') is None or libraries.get('sounddevice') is None):
            library_waiting_queue.append(self)
            self.set_sensitive(False)

    def set_active(self, state):
        self.button.set_active(state)

    def get_active(self) -> bool:
        return self.button.get_active()

    def play_audio_queue(self):
        while True:
            audio = self.play_queue.get()
            if audio is None or not self.get_active():
                return
            libraries.get('sounddevice').play(audio, samplerate=24000)
            libraries.get('sounddevice').wait()

    def run_tts(self):
        global tts_engine, tts_engine_language
        GLib.idle_add(self.set_visible_child_name, 'loading')

        # Get Voice
        voice = None
        if self.message_element.get_model():
            voice = SQL.get_model_preferences(self.message_element.get_model()).get('voice', None)
        if not voice:
            voice = TTS_VOICES.get(list(TTS_VOICES.keys())[self.message_element.get_root().settings.get_value('tts-model').unpack()])

        # Show Voice in Model Manager if Needed
        if not models.tts_model_exists(voice):
            tts_path = models.get_tts_path()
            if tts_path:
                models.common.append_added_model(self.message_element.get_root(), models.speech.TextToSpeechModelButton(os.path.join(tts_path, voice + '.pt')))

        # Generate TTS_ENGINE if needed
        if not tts_engine or tts_engine_language != voice[0]:
            tts_engine = libraries.get('kokoro').KPipeline(lang_code=voice[0], repo_id='hexgrad/Kokoro-82M')
            tts_engine_language=voice[0]

        # Start Generation of Audio and Start Playing
        play_thread = threading.Thread(target=self.play_audio_queue, daemon=True)
        play_thread.start()
        queue_index = 0
        GLib.idle_add(self.message_element.remove_css_class, 'tts_message_loading')
        GLib.idle_add(self.message_element.add_css_class, 'tts_message')
        GLib.idle_add(self.set_visible_child_name, 'button')
        generator = None
        while queue_index + 1 < len(self.message_element.get_content_for_dictation()) or any([isinstance(b, blocks.text.GeneratingText) for b in list(self.message_element.block_container)]):
            text = self.message_element.get_content_for_dictation()
            end_index = max(text.rfind("\n"), text.rfind("."), text.rfind("?"), text.rfind("!"), text.rfind(":"))
            if end_index == -1 or end_index < queue_index:
                end_index = len(text)
            if text[queue_index:end_index]:
                generator = tts_engine(
                    text[queue_index:end_index],
                    voice=voice,
                    speed=1.2,
                    split_pattern=r'\n+'
                )
                for gs, ps, audio in generator:
                    self.play_queue.put(audio)
            else:
                time.sleep(1)
                if not any([isinstance(b, blocks.text.GeneratingText) for b in list(self.message_element.block_container)]):
                    break
            if not self.get_active():
                return
            queue_index = end_index
        if generator:
            del generator
        gc.collect()
        self.play_queue.put(None)
        play_thread.join()
        self.set_active(False)

    def dictate_message(self, button):
        global message_dictated
        if not self.message_element.get_root():
            return

        if button.get_active():
            GLib.idle_add(self.message_element.add_css_class, 'tts_message_loading')
            if message_dictated and message_dictated.popup.tts_button.get_active():
                 message_dictated.popup.tts_button.set_active(False)
            message_dictated = self.message_element
            self.play_queue = queue.Queue()
            generation_thread = threading.Thread(target=self.run_tts, daemon=True).start()
        else:
            GLib.idle_add(self.message_element.remove_css_class, 'tts_message_loading')
            GLib.idle_add(self.message_element.remove_css_class, 'tts_message')
            GLib.idle_add(self.set_visible_child_name, 'button')
            message_dictated = None
            threading.Thread(target=libraries.get('sounddevice').stop, daemon=True).start()

class MicrophoneButton(Gtk.Stack):
    __gtype_name__ = 'AlpacaMicrophoneButton'

    def __init__(self, text_view):
        self.text_view = text_view

        super().__init__(
            visible = importlib.util.find_spec('whisper') and importlib.util.find_spec('pyaudio')
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
        model_name = list(STT_MODELS)[self.get_root().settings.get_value('stt-model').unpack()]
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
            button.get_parent().set_visible_child_name("loading")
            button.add_css_class('accent')

            samplerate=16000
            model = None

            self.mic_timeout=0

            try:
                if not loaded_whisper_models.get(model_name):
                    loaded_whisper_models[model_name] = libraries.get('whisper').load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
                if pulling_model:
                    threading.Thread(target=pulling_model.update_progressbar, args=({'status': 'success'},)).start()
            except Exception as e:
                dialog.simple_error(
                    parent = button.get_root(),
                    title = _('Speech Recognition Error'),
                    body = _('An error occurred while pulling speech recognition model'),
                    error_log = e
                )
                logger.error(e)
                return
            button.get_parent().set_visible_child_name("button")

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
                        threading.Thread(target=recognize_audio, args=(loaded_whisper_models.get(model_name), audio_data, buffer.get_end_iter()), daemon=True).start()

                        if self.mic_timeout >= 2 and mic_auto_send and buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False):
                            GLib.idle_add(self.text_view.parent_footer.send_callback)
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
            pulling_model = models.pulling.PullingModelButton(
                model_name,
                lambda model_name, window=button.get_root(): models.common.prepend_added_model(window, models.speech.SpeechToTextModelButton(model_name)),
                None,
                False
            )
            models.common.prepend_added_model(button.get_root(), pulling_model)
            threading.Thread(target=run_mic, args=(pulling_model,), daemon=True).start()

        if button.get_active():
            if os.path.isfile(os.path.join(data_dir, 'whisper', '{}.pt'.format(model_name))):
                if message_dictated:
                    message_dictated.popup.tts_button.set_active(False)
                threading.Thread(target=run_mic, daemon=True).start()
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

class TranscriptionPage(Adw.Bin):
    __gtype_name__ = 'AlpacaTranscriptionPage'

    def __init__(self, attachment_func:callable, file_path:str):
        self.attachment_func = attachment_func
        self.file_path = file_path
        self.pulling_model = None

        super().__init__(
            child=Adw.StatusPage(
                title=_('Transcribing Audio'),
                description=os.path.basename(self.file_path),
                child=Adw.Spinner()
            )
        )

        # Activities
        self.buttons = []
        self.title = _("Transcriber")
        self.activity_icon = 'music-note-single-symbolic'

    def prepare_transcription(self, pulling_model:Gtk.Widget=None):
        self.pulling_model = pulling_model
        threading.Thread(target=self.run_transcription).start()

    def run_transcription(self):
        model_name = list(STT_MODELS)[self.get_root().settings.get_value('stt-model').unpack()]
        try:
            if not loaded_whisper_models.get(model_name):
                loaded_whisper_models[model_name] = libraries.get('whisper').load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
            if self.pulling_model:
                threading.Thread(target=self.pulling_model.update_progressbar, args=({'status': 'success'},)).start()
        except Exception as e:
            dialog.simple_error(
                parent = self.get_root(),
                title = _('Transcription Error'),
                body = _('An error occurred while pulling speech recognition model'),
                error_log = e
            )
            logger.error(e)
            self.close()
            return
        try:
            result = loaded_whisper_models.get(model_name).transcribe(self.file_path, word_timestamps=False)
            segments = result['segments']
            paragraphs = []
            current_para = []

            for i, seg in enumerate(segments):
                current_para.append(seg['text'].strip())
                if i + 1 < len(segments):
                    if segments[i+1]['start'] - seg['end'] > 1.2:
                        paragraphs.append(' '.join(current_para))
                        current_para = []
            if current_para:
                paragraphs.append(' '.join(current_para))

            self.attachment_func('\n\n'.join(paragraphs))
            self.close()

        except Exception as e:
            dialog.simple_error(
                parent = self.get_root(),
                title = _('Transcription Error'),
                body = _('An error occurred while transcribing audio'),
                error_log = e
            )
            logger.error(e)
            self.close()
            return

    def close(self):
        # Try tab
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.close_page(self.get_parent().tab)
        else:
            # Try dialog
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()

    def on_close(self):
        pass

    def on_reload(self):
        pass

def transcribe_audio_file(root:Gtk.Widget, attachment_func:callable, file_path:str):
    def show_activity(pulling_model=None):
        page = TranscriptionPage(attachment_func, file_path)
        activities.show_activity(page, root)
        page.prepare_transcription(pulling_model)

    def prepare_download():
        window=root.get_application().main_alpaca_window
        pulling_model = models.pulling.PullingModelButton(
            model_name,
            lambda model_name: models.common.prepend_added_model(window, models.speech.SpeechToTextModelButton(model_name)),
            None,
            False
        )
        models.common.prepend_added_model(window, pulling_model)
        show_activity(pulling_model)

    model_name = list(STT_MODELS)[root.settings.get_value('stt-model').unpack()]
    if os.path.isfile(os.path.join(data_dir, 'whisper', '{}.pt'.format(model_name))):
        show_activity()
    else:
        dialog.simple(
            parent = root,
            heading = _("Download Speech Recognition Model"),
            body = _("To use speech recognition you'll need to download a special model ({})").format(STT_MODELS.get(model_name, '~151mb')),
            callback = prepare_download,
            button_name = _("Download Model")
        )
