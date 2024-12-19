#generic_actions.py
"""
Working on organizing the code
"""

import os, requests
from youtube_transcript_api import YouTubeTranscriptApi
from html2text import html2text
from .internal import cache_dir

window = None

def connect_remote(remote_url:str, bearer_token:str):
    if remote_url.endswith('/'):
        remote_url = remote_url.rstrip('/')
    if not (remote_url.startswith('http://') or remote_url.startswith('https://')):
        remote_url = f'http://{remote_url}'
    window.ollama_instance.remote_url=remote_url
    window.ollama_instance.bearer_token=bearer_token
    window.ollama_instance.remote = True
    window.ollama_instance.stop()
    window.model_manager.update_local_list()
    window.save_server_config()
    window.remote_connection_selector.set_subtitle(remote_url)

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

    result_text += '\n'.join([t['text'] for t in transcript])

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
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), textview_text, len(textview_text))
        if not os.path.exists('/tmp/alpaca/websites/'):
            os.makedirs('/tmp/alpaca/websites/')
        md_name = window.generate_numbered_name('website.md', os.listdir('/tmp/alpaca/websites'))
        file_path = os.path.join('/tmp/alpaca/websites/', md_name)
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
                "l", "cu", "dockerfile", "glsl", "g", "lua", "php", "rb", "ru", "rs", "sql", "sh", "p8"],
        "image": ["png", "jpeg", "jpg", "webp", "gif"],
        "pdf": ["pdf"],
        "odt": ["odt"]
    }
    extension = file.get_path().split(".")[-1]
    file_type = next(key for key, value in file_types.items() if extension in value)
    if not file_type:
        return
    if file_type == 'image' and not window.model_manager.verify_if_image_can_be_used():
        window.show_toast(_("Image recognition is only available on specific models"), window.main_overlay)
        return
    window.attach_file(file.get_path(), file_type)
