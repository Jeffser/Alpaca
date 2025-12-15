# voice.py
"""
Manages TTS and STT code
"""


import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ..sql_manager import Instance as SQL, prettify_model_name
from ..constants import data_dir, cache_dir, STT_MODELS, SPEACH_RECOGNITION_LANGUAGES, TTS_VOICES
from . import dialog, models, blocks, activities, message

import os, threading, importlib.util, re, unicodedata, gc, queue, time, logging, wave
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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/voice/dictate_button.ui')
class DictateButton(Gtk.Stack):
    __gtype_name__ = 'AlpacaDictateButton'

    button = Gtk.Template.Child()

    def __init__(self):
        super().__init__(
            visible = importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice')
        )
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
        message_element = self.get_ancestor(message.Message)
        # Get Voice
        voice = None
        if message_element.get_model():
            voice = SQL.get_model_preferences(message_element.get_model()).get('voice', None)
        if not voice:
            voice = TTS_VOICES.get(list(TTS_VOICES.keys())[message_element.get_root().settings.get_value('tts-model').unpack()])

        speed = message_element.get_root().settings.get_value('tts-speed').unpack()

        # Show Voice in Model Manager if Needed
        if not models.common.tts_model_exists(voice):
            tts_path = models.get_tts_path()
            if tts_path:
                model_element = models.create_tts_model(os.path.join(tts_path, voice + '.pt'))
                models.common.append_added_model(message_element.get_root(), model_element)

        # Generate TTS_ENGINE if needed
        if not tts_engine or tts_engine_language != voice[0]:
            tts_engine = libraries.get('kokoro').KPipeline(lang_code=voice[0], repo_id='hexgrad/Kokoro-82M')
            tts_engine_language=voice[0]

        # Start Generation of Audio and Start Playing
        play_thread = threading.Thread(target=self.play_audio_queue, daemon=True)
        play_thread.start()
        queue_index = 0
        GLib.idle_add(message_element.remove_css_class, 'tts_message_loading')
        GLib.idle_add(message_element.add_css_class, 'tts_message')
        GLib.idle_add(self.set_visible_child_name, 'button')
        generator = None
        while queue_index + 1 < len(message_element.get_content_for_dictation()) or any([isinstance(b, blocks.text.GeneratingText) for b in list(message_element.block_container)]):
            text = message_element.get_content_for_dictation()
            end_index = max(text.rfind("\n"), text.rfind("."), text.rfind("?"), text.rfind("!"), text.rfind(":"))
            if end_index == -1 or end_index < queue_index:
                end_index = len(text)
            if text[queue_index:end_index]:
                generator = tts_engine(
                    text[queue_index:end_index],
                    voice=voice,
                    speed=speed,
                    split_pattern=r'\n+'
                )
                for gs, ps, audio in generator:
                    self.play_queue.put(audio)
            else:
                time.sleep(1)
                if not any([isinstance(b, blocks.text.GeneratingText) for b in list(message_element.block_container)]):
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

    @Gtk.Template.Callback()
    def dictate_message(self, button):
        global message_dictated
        message_element = self.get_ancestor(message.Message)
        if not message_element.get_root():
            return

        if button.get_active():
            GLib.idle_add(message_element.add_css_class, 'tts_message_loading')
            if message_dictated and message_dictated.popup.tts_button.get_active():
                 message_dictated.popup.tts_button.set_active(False)
            message_dictated = message_element
            self.play_queue = queue.Queue()
            generation_thread = threading.Thread(target=self.run_tts, daemon=True).start()
        else:
            GLib.idle_add(message_element.remove_css_class, 'tts_message_loading')
            GLib.idle_add(message_element.remove_css_class, 'tts_message')
            GLib.idle_add(self.set_visible_child_name, 'button')
            message_dictated = None
            threading.Thread(target=libraries.get('sounddevice').stop, daemon=True).start()

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/voice/microphone_button.ui')
class MicrophoneButton(Gtk.Stack):
    __gtype_name__ = 'AlpacaMicrophoneButton'

    button = Gtk.Template.Child()

    def __init__(self):
        self.text_view = None
        self.mic_timeout = 0
        self.pulling_model = None

        super().__init__(
            visible = importlib.util.find_spec('whisper') and importlib.util.find_spec('pyaudio')
        )

        if self.get_visible() and (libraries.get('whisper') is None or libraries.get('pyaudio') is None):
            library_waiting_queue.append(self)
            self.set_sensitive(False)

    def set_text_view(self, text_view):
        self.text_view = text_view

    @Gtk.Template.Callback()
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

        def run_mic():
            button.get_parent().set_visible_child_name("loading")
            button.add_css_class('accent')

            samplerate=16000
            model = None

            self.mic_timeout=0

            try:
                if not loaded_whisper_models.get(model_name):
                    loaded_whisper_models[model_name] = libraries.get('whisper').load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
                if self.pulling_model:
                    self.pulling_model.update_progressbar(-1)
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
                    mic_auto_send = self.get_root().settings.get_value('stt-auto-send').unpack() and hasattr(self.text_view, 'parent_footer')
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
            self.pulling_model = models.create_stt_model(model_name)
            self.pulling_model.update_progressbar(1)
            models.common.prepend_added_model(button.get_root(), self.pulling_model)
            threading.Thread(target=run_mic, daemon=True).start()

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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/voice/podcast_dialog.ui')
class PodcastDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaPodcastDialog'

    main_stack = Gtk.Template.Child()

    title_voice_combo = Gtk.Template.Child()
    user_voice_combo = Gtk.Template.Child()
    system_voice_combo = Gtk.Template.Child()

    model_group = Gtk.Template.Child()

    progress_status_page = Gtk.Template.Child()

    sample_rate = 24000

    def __init__(self, chat):
        self.chat = chat
        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        super().__init__()
        self.set_title(self.chat.get_name())
        self.final_audio = []
        threading.Thread(target=self.prepare_preferences_page, daemon=True).start()

    def prepare_preferences_page(self):
        # run in separate thread
        if len(list(self.chat.container)) == 0: #maybe not loaded
            self.chat.load_messages()

        self.default_index = self.settings.get_value('tts-model').unpack()

        model_combo_model = Gtk.StringList() # for model voices
        simple_combo_model = Gtk.StringList() # for general voices
        simple_combo_model.append(_("Skip"))

        for name in TTS_VOICES:
            model_combo_model.append(name)
            simple_combo_model.append(name)

        GLib.idle_add(self.title_voice_combo.set_model, simple_combo_model)
        GLib.idle_add(self.user_voice_combo.set_model, simple_combo_model)
        GLib.idle_add(self.system_voice_combo.set_model, simple_combo_model)
        GLib.idle_add(self.user_voice_combo.set_selected, self.default_index+1)


        self.added_models = []
        for message_element in list(self.chat.container):
            if message_element.mode == 1 and message_element.author:
                if message_element.author not in [m.get_name() for m in self.added_models]:
                    voice_id = SQL.get_model_preferences(message_element.author).get('voice', None)
                    voice_index = self.default_index
                    if voice_id in list(TTS_VOICES.values()):
                        voice_index = list(TTS_VOICES.values()).index(voice_id)

                    combo_element = Adw.ComboRow(
                        title=prettify_model_name(message_element.author),
                        name=message_element.author,
                        model=model_combo_model
                    )
                    combo_element.set_selected(voice_index)
                    GLib.idle_add(self.model_group.add, combo_element)
                    self.added_models.append(combo_element)

        if len(self.added_models) == 0:
            GLib.idle_add(dialog.show_toast,
                _("This chat has no model messages"),
                self.get_root()
            )
            GLib.idle_add(self.force_close)

    def get_title_voice_id(self) -> str or None:
        if self.title_voice_combo.get_selected() == 0:
            return None
        else:
            return TTS_VOICES.get(self.title_voice_combo.get_selected_item().get_string())

    def get_user_voice_id(self) -> str or None:
        if self.user_voice_combo.get_selected() == 0:
            return None
        else:
            return TTS_VOICES.get(self.user_voice_combo.get_selected_item().get_string())

    def get_system_voice_id(self) -> str or None:
        if self.system_voice_combo.get_selected() == 0:
            return None
        else:
            return TTS_VOICES.get(self.system_voice_combo.get_selected_item().get_string())

    def get_model_voice_id(self, model_name:str) -> str or None:
        model_element_names = [m.get_name() for m in self.added_models]
        if model_name not in model_element_names:
            return list(TTS_VOICES.values())[self.default_index]

        model_element = self.added_models[model_element_names.index(model_name)]
        return TTS_VOICES[model_element.get_selected_item().get_string()]

    def generate_audio(self, voice_id:str, content:str):
        kokoro = libraries.get('kokoro')
        speed = self.settings.get_value('tts-speed').unpack()
        pipeline = kokoro.KPipeline(lang_code=voice_id[0])
        generator = pipeline(content, voice=voice_id, speed=speed, split_pattern=r'\n+')
        for gs, ps, audio in generator:
            self.final_audio.append(audio)

    def generate(self):
        # run in separate thread
        self.set_can_close(False)
        GLib.idle_add(self.main_stack.set_visible_child_name, 'progress')

        gap_seconds = 0.3
        silence = np.zeros(int(self.sample_rate * gap_seconds), dtype=np.float32)

        message_list = list(self.chat.container)
        self.final_audio = []

        self.progress_status_page.set_description('{} / {}'.format(0, len(message_list)))

        title_voice_id = self.get_title_voice_id()
        if title_voice_id:
            allowed_characters = (',', '.', ':', ';', '+', '/', '-', '(', ')', '[', ']', '=', '<', '>', '’', '\'', '"', '¿', '?', '¡', '!')
            cleaned_text = ''.join(c for c in self.chat.get_name() if unicodedata.category(c).startswith(('L', 'N', 'Zs')) or c in allowed_characters)
            self.generate_audio(title_voice_id, cleaned_text)

        for i, message in enumerate(message_list):
            voice_id = None
            if message.mode == 0:
                voice_id = self.get_user_voice_id()
            elif message.mode == 1 and message.author:
                voice_id = self.get_model_voice_id(message.author)
            elif message.mode == 2:
                voice_id = self.get_system_voice_id()

            if voice_id:
                content = message.get_content_for_dictation()
                if content:
                    self.generate_audio(voice_id, content)
                    if not self.get_root():
                        return
                    self.final_audio.append(silence)
                    self.progress_status_page.set_description('{} / {}'.format(i+1, len(message_list)))
                    self.progress_status_page.get_child().set_fraction((i+1)/len(message_list))

        if len(self.final_audio) <= 1:
            self.cancel()

        # Remove final silence
        self.final_audio = self.final_audio[:-1]
        self.final_audio = np.concatenate(self.final_audio)
        self.set_can_close(True)
        GLib.idle_add(self.main_stack.set_visible_child_name, 'ready')

    @Gtk.Template.Callback()
    def generate_requested(self, button):
        threading.Thread(target=self.generate).start()

    def export(self, file_dialog, result, gdata):
        file = file_dialog.save_finish(result)
        if file and file.get_path():
            audio_int16 = (self.final_audio * 32767).astype(np.int16)
            with wave.open(file.get_path(), 'w') as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())
            dialog.show_toast(
                message=_("Podcast exported successfully"),
                root_widget=self.get_root()
            )
            self.force_close()

    @Gtk.Template.Callback()
    def export_requested(self, button):
        file_dialog = Gtk.FileDialog(
            initial_name='{}.wav'.format(self.chat.get_name().replace('/', ' '))
        )
        file_dialog.save(self.get_root(), None, self.export, None)

    @Gtk.Template.Callback()
    def cancel(self, button):
        self.force_close()

    @Gtk.Template.Callback()
    def close_attempted(self, dia):
        if self.get_can_close():
            self.force_close()
        else:
            dialog.simple(
                parent=self.get_root(),
                heading=_("Stop Generation"),
                body=_("Are you sure you want to stop the podcast generation?"),
                callback=self.force_close,
                button_name=_("Stop"),
                button_appearance="destructive"
            )
        return True
