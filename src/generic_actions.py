#generic_actions.py
"""
Working on organizing the code
"""

import gi
from gi.repository import GLib
import os, requests, re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from html2text import html2text
from .internal import cache_dir
from .custom_widgets import model_manager_widget

window = None

def attach_youtube(video_title:str, video_author:str, watch_url:str, video_url:str, video_id:str, caption_name:str):
    buffer = window.message_text_view.get_buffer()
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).replace(video_url, "")
    buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
    buffer.insert(buffer.get_start_iter(), text, len(text))

    result_text = "{}\n{}\n{}\n\n".format(video_title, video_author, watch_url)
    caption_name = caption_name.split(' (')[-1][:-1]

    if caption_name.startswith('Translate:'):
        available_captions = get_youtube_transcripts(video_id)
        original_caption_name = available_captions[0].split(' (')[-1][:-1]
        transcript = YouTubeTranscriptApi.list_transcripts(video_id).find_transcript([original_caption_name]).translate(caption_name.split(':')[-1]).fetch()
        result_text += '(Auto translated from {})\n'.format(available_captions[0])
    else:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[caption_name])

    result_text += TextFormatter().format_transcript(transcript)
    #result_text += '\n'.join([t['text'] for t in transcript])

    if not os.path.exists(os.path.join(cache_dir, 'tmp/youtube')):
        os.makedirs(os.path.join(cache_dir, 'tmp/youtube'))
    file_path = os.path.join(os.path.join(cache_dir, 'tmp/youtube'), '{} ({})'.format(video_title.replace('/', ' '), caption_name))
    with open(file_path, 'w+', encoding="utf-8") as f:
        f.write(result_text)

    window.attach_file(file_path, 'youtube')

def get_youtube_transcripts(video_id:str):
    return ['{} ({})'.format(t.language, t.language_code) for t in YouTubeTranscriptApi.list_transcripts(video_id)]

def attach_website(url:str):
    response = requests.get(url)
    if response.status_code == 200:
        html = response.text
        md = html2text(html)
        buffer = window.message_text_view.get_buffer()
        textview_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).replace(url, "")
        GLib.idle_add(buffer.delete, buffer.get_start_iter(), buffer.get_end_iter())
        GLib.idle_add(buffer.insert, buffer.get_start_iter(), textview_text, len(textview_text))

        if not os.path.exists('/tmp/alpaca/websites/'):
            os.makedirs('/tmp/alpaca/websites/')

        website_title = 'website'
        match = re.search(r'^# (.+)', md, re.MULTILINE)
        if match:
            website_title = match.group(1)
        else:
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if match:
                website_title = match.group(1)
        website_title = window.generate_numbered_name(website_title, os.listdir('/tmp/alpaca/websites'))

        file_path = os.path.join('/tmp/alpaca/websites/', website_title)
        with open(file_path, 'w+', encoding="utf-8") as f:
            f.write('{}\n\n{}'.format(url, md))
        window.attach_file(file_path, 'website')
    else:
        window.show_toast(_("An error occurred while extracting text from the website"), window.main_overlay)

def attach_file(file):
    file_types = {
        "plain_text": ["txt", "md"],
        "code": ["c", "h", "css", "html", "js", "ts", "py", "java", "json", "xml", "asm", "nasm",
                "cs", "csx", "cpp", "cxx", "cp", "hxx", "inc", "csv", "lsp", "lisp", "el", "emacs",
                "l", "cu", "dockerfile", "glsl", "g", "lua", "php", "rb", "ru", "rs", "sql", "sh", "p8",
                "yaml"],
        "image": ["png", "jpeg", "jpg", "webp", "gif"],
        "pdf": ["pdf"],
        "odt": ["odt"]
    }
    if file.query_info("standard::content-type", 0, None).get_content_type() == 'text/plain':
        extension = 'txt'
    else:
        extension = file.get_path().split(".")[-1]
    found_types = [key for key, value in file_types.items() if extension in value]
    if len(found_types) == 0:
        file_type = 'plain_text'
    else:
        file_type = found_types[0]
    if file_type == 'image' and not model_manager_widget.get_selected_model().get_vision():
        window.show_toast(_("Image recognition is only available on specific models"), window.main_overlay)
        return
    window.attach_file(file.get_path(), file_type)
