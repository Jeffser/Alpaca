# transcriber.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ...constants import IN_FLATPAK, data_dir, REMBG_MODELS, STT_MODELS
from .. import dialog, attachments, models, chat, message, models, instances, voice
from ...sql_manager import generate_uuid, prettify_model_name, Instance as SQL
import base64, os, threading, datetime, logging

logger = logging.getLogger(__name__)

class Transcriber(Gtk.Stack):
    __gtype_name__ = 'AlpacaTranscriber'

    def __init__(self, audio_file:Gio.File=None):

        super().__init__(
            transition_type=1
        )

        button_container = Gtk.Box(
            halign=3,
            orientation=1,
            spacing=10
        )
        select_mic_button = Gtk.Button(
            child=Adw.ButtonContent(
                label=_('Microphone'),
                icon_name='audio-input-microphone-symbolic'
            ),
            tooltip_text=_('Microphone'),
            css_classes=['pill']
        )
        select_mic_button.connect('clicked', lambda btn: self.use_microphone())
        button_container.append(select_mic_button)
        select_file_button = Gtk.Button(
            child=Adw.ButtonContent(
                label=_('File'),
                icon_name='chain-link-loose-symbolic'
            ),
            tooltip_text=_('File'),
            css_classes=['pill']
        )
        select_file_button.connect('clicked', lambda btn: self.use_file())
        button_container.append(select_file_button)

        # MAIN
        self.add_named(
            Adw.StatusPage(
                title=_('Transcriber'),
                description=_('Transcribe audio files or your voice.'),
                icon_name='music-note-single-symbolic',
                child=button_container
            ),
            'main'
        )

        # LOADING FILE
        self.add_named(
            Adw.StatusPage(
                title=_('Transcribing Audio'),
                child=Adw.Spinner()
            ),
            'loading_file'
        )

        # MICROPHONE / RESULTS
        self.result_textview = Gtk.TextView(
            wrap_mode=3,
            left_margin=10,
            right_margin=10,
            top_margin=10,
            bottom_margin=10
        )
        result_scroller = Gtk.ScrolledWindow(
            propagate_natural_height=True,
            overflow=1,
            css_classes=['card', 'undershoot-bottom'],
            child=self.result_textview,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
            valign=3
        )
        self.microphone_button = voice.MicrophoneButton(
            self.result_textview
        )
        self.microphone_button.set_visible(False)

        self.add_named(
            result_scroller,
            'results'
        )

        self.attachment_name = _('Transcription')
        if audio_file:
            self.attachment_name = os.path.basename(audio_file.get_path())
        self.attachment_button = Gtk.Button(
            icon_name='chain-link-loose-symbolic',
            tooltip_text=_('Attach'),
            css_classes=['br0', 'flat'],
            visible=False
        )
        self.attachment_button.connect("clicked", lambda button: self.attach_results())

        # Activity
        self.buttons = [self.attachment_button, self.microphone_button]
        self.title = _('Transcriber')
        self.activity_icon = 'music-note-single-symbolic'

        if audio_file:
            self.connect('realize', lambda *_: self.use_file(audio_file))

    def attach_results(self):
        buffer = self.result_textview.get_buffer()
        result_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        attachment = attachments.Attachment(
            file_id='-1',
            file_name=self.attachment_name,
            file_type='audio',
            file_content=result_text
        )
        self.get_root().get_application().main_alpaca_window.global_footer.attachment_container.add_attachment(attachment)

    def prepare_download(self, model_name:str, audio_file:Gio.File):
        pulling_model = models.pulling.PullingModelButton(
            model_name,
            lambda model_name, window=self.get_root(): models.common.prepend_added_model(window, models.speech.SpeechToTextModelButton(model_name)),
            None,
            False
        )
        models.common.prepend_added_model(self.get_root(), pulling_model)
        self.set_visible_child_name('loading_file')
        threading.Thread(target=self.run_file_transcription, args=(audio_file.get_path(), pulling_model,), daemon=True).start()

    def on_attachment(self, audio_file:Gio.File):
        if not audio_file:
            return
        self.attachment_name = os.path.basename(audio_file.get_path())
        self.get_child_by_name('loading_file').set_description(self.attachment_name)

        model_name = list(STT_MODELS)[self.get_root().settings.get_value('stt-model').unpack()]
        if os.path.isfile(os.path.join(data_dir, 'whisper', '{}.pt'.format(model_name))):
            self.set_visible_child_name('loading_file')
            threading.Thread(target=self.run_file_transcription, args=(audio_file.get_path(),), daemon=True).start()
        else:
            dialog.simple(
                parent = self.get_root(),
                heading = _("Download Speech Recognition Model"),
                body = _("To use speech recognition you'll need to download a special model ({})").format(STT_MODELS.get(model_name, '~151mb')),
                callback = lambda model=model_name, file=audio_file: self.prepare_download(model, file),
                button_name = _("Download Model")
            )

    def use_microphone(self):
        self.microphone_button.set_visible(True)
        self.attachment_button.set_visible(True)
        self.set_visible_child_name('results')
        GLib.idle_add(self.microphone_button.button.set_active, True)

    def use_file(self, audio_file:Gio.File=None):
        self.microphone_button.set_visible(False)
        self.attachment_button.set_visible(False)

        if audio_file:
            self.on_attachment(audio_file)
        else:
            ff = Gtk.FileFilter()
            ff.set_name(_('Audio and video files'))
            file_filters = [ff]

            mimes = []
            audio_mimes = ('wav', 'mpeg', 'flac', 'x-flac', 'ogg', 'mp4', 'x-m4a', 'aac', 'aiff', 'x-aiff', 'opus', 'webm')
            for m in audio_mimes:
                mimes.append('audio/{}'.format(m))
            video_mimes = ('mp4', 'x-matroska', 'quicktime', 'x-msvideo', 'webm')
            for m in video_mimes:
                mimes.append('video/{}'.format(m))

            for mime in mimes:
                ff = Gtk.FileFilter()
                ff.add_mime_type(mime)
                file_filters[0].add_mime_type(mime)
                file_filters.append(ff)

            dialog.simple_file(
                parent = self.get_root(),
                file_filters = file_filters,
                callback = self.on_attachment
            )

    def run_file_transcription(self, file_path:str, pulling_model=None):
        model_name = list(STT_MODELS)[self.get_root().settings.get_value('stt-model').unpack()]
        try:
            if not voice.loaded_whisper_models.get(model_name):
                voice.loaded_whisper_models[model_name] = voice.libraries.get('whisper').load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
            if pulling_model:
                threading.Thread(target=pulling_model.update_progressbar, args=({'status': 'success'},)).start()
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
            result = voice.loaded_whisper_models.get(model_name).transcribe(file_path, word_timestamps=False)
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

            result_text = '\n\n'.join(paragraphs)
            GLib.idle_add(self.result_textview.get_buffer().set_text, result_text, len(result_text.encode('utf-8')))
            GLib.idle_add(self.set_visible_child_name, 'results')
            GLib.idle_add(self.attachment_button.set_visible, True)

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
