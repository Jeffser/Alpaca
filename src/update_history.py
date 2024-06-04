# update_history.py
# This script updates the old chats.json file to the structure needed for the new version
import os, json, base64
from PIL import Image
import io


def update(self):
    old_data = None
    new_data = {"chats": {}}
    with open(os.path.join(self.config_dir, "chats.json"), 'r') as f:
        old_data = json.load(f)["chats"]
    for chat_name, content in old_data.items():
        directory = os.path.join(self.data_dir, "chats", chat_name)
        if not os.path.exists(directory): os.makedirs(directory)
        new_messages = {}
        for message in content['messages']:
            message_id = self.generate_uuid()
            if 'images' in message:
                if not os.path.exists(os.path.join(directory, message_id)): os.makedirs(os.path.join(directory, message_id))
                new_images = []
                for image in message['images']:
                    file_name = f"{self.generate_uuid()}.png"
                    decoded = base64.b64decode(image)
                    buffer = io.BytesIO(decoded)
                    im = Image.open(buffer)
                    im.save(os.path.join(directory, message_id, file_name))
                    new_images.append(file_name)
                message['images'] = new_images
            new_messages[message_id] = message
        new_data['chats'][chat_name] = {}
        new_data['chats'][chat_name]['messages'] = new_messages

    with open(os.path.join(self.data_dir, "chats", "chats.json"), "w+") as f:
        json.dump(new_data, f, indent=6)


