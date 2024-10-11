#generic_actions.py
"""
Working on organizing the code
"""

import os, requests
from pytube import YouTube
from html2text import html2text
from .internal import cache_dir

window = None

def connect_local():
    window.remote_connection_switch.set_active(False)

def connect_remote(url:str, bearer:str):
    window.remote_connection_entry.set_text(url)
    window.remote_bearer_token_entry.set_text(bearer)
    window.remote_connection_switch.set_active(True)

def attach_youtube(video_url:str, caption_name:str):
    buffer = window.message_text_view.get_buffer()
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).replace(video_url, "")
    buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
    buffer.insert(buffer.get_start_iter(), text, len(text))

    yt = YouTube(video_url)
    text = "{}\n{}\n{}\n\n".format(yt.title, yt.author, yt.watch_url)

    for event in yt.captions[caption_name.split('(')[-1][:-1]].json_captions['events']:
        text += "{}\n".format(event['segs'][0]['utf8'].replace('\n', '\\n'))
    if not os.path.exists(os.path.join(cache_dir, 'tmp/youtube')):
        os.makedirs(os.path.join(cache_dir, 'tmp/youtube'))
    file_path = os.path.join(os.path.join(cache_dir, 'tmp/youtube'), f'{yt.title} ({caption_name.split(" (")[0]})')
    with open(file_path, 'w+', encoding="utf-8") as f:
        f.write(text)

    window.attach_file(file_path, 'youtube')

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
        "plain_text": ["txt", "md", "html", "css", "js", "py", "java", "json", "xml"],
        "image": ["png", "jpeg", "jpg", "webp", "gif"],
        "pdf": ["pdf"]
    }
    extension = file.get_path().split(".")[-1]
    file_type = next(key for key, value in file_types.items() if extension in value)
    if not file_type:
        return
    if file_type == 'image' and not window.model_manager.verify_if_image_can_be_used():
        window.show_toast(_("Image recognition is only available on specific models"), window.main_overlay)
        return
    window.attach_file(file.get_path(), file_type)
