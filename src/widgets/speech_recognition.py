# speech_recognition.py

import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf
from ..sql_manager import Instance as SQL
from ..constants import data_dir, STT_MODELS, SPEACH_RECOGNITION_LANGUAGES
from . import dialog, model_manager

import os, threading, importlib.util
import numpy as np

class MicrophoneButton(Gtk.Stack):
    __gtype_name__ = 'AlpacaMicrophoneButton'

    def __init__(self, text_view):
        self.text_view = text_view

        super().__init__(
            visible = importlib.util.find_spec('whisper')
        )
        button = Gtk.ToggleButton(
            icon_name='audio-input-microphone-symbolic',
            tooltip_text=_('Use Speech Recognition'),
            css_classes=['microphone_button']
        )
        button.connect('toggled', self.toggled)
        self.add_named(button, 'button')
        self.add_named(Adw.Spinner(css_classes=['p10']), 'loading')
        self.mic_timeout = 0

    def toggled(self, button):
        language=SPEACH_RECOGNITION_LANGUAGES[self.get_root().settings.get_value('stt-language').unpack()]
        buffer = self.text_view.get_buffer()
        model_name = os.getenv("ALPACA_SPEECH_MODEL", "base")

        def recognize_audio(model, audio_data, current_iter):
            result = model.transcribe(audio_data, language=language)
            if len(result.get("text").encode('utf8')) == 0:
                self.mic_timeout += 1
            else:
                GLib.idle_add(buffer.insert, current_iter, result.get("text"), len(result.get("text").encode('utf8')))
                self.mic_timeout = 0

        def run_mic(pulling_model:Gtk.Widget=None):
            GLib.idle_add(button.get_parent().set_visible_child_name, "loading")
            import whisper
            import pyaudio
            GLib.idle_add(button.add_css_class, 'accent')

            samplerate=16000
            p = pyaudio.PyAudio()
            model = None

            self.mic_timeout=0

            try:
                model = whisper.load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
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

            if model:
                stream = p.open(
                    format=pyaudio.paInt16,
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
                        threading.Thread(target=recognize_audio, args=(model, audio_data, buffer.get_end_iter())).start()

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
                    p.terminate()

            if button.get_active():
                button.set_active(False)

        def prepare_download():
            if button.get_root().get_name() == 'AlpacaWindow':
                pulling_model = model_manager.PullingModel(model_name, model_manager.add_speech_to_text_model, False)
                button.get_root().local_model_flowbox.prepend(pulling_model)
            threading.Thread(target=run_mic, args=(pulling_model,)).start()

        if button.get_active():
            if os.path.isfile(os.path.join(data_dir, 'whisper', '{}.pt'.format(model_name))):
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
