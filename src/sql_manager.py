# sql_manager.py

import sqlite3, uuid, datetime, os, shutil, json
from .internal import data_dir
from . import instance_manager

def generate_uuid() -> str:
    return f"{datetime.datetime.today().strftime('%Y%m%d%H%M%S%f')}{uuid.uuid4().hex}"

def generate_numbered_name(name:str, compare_list:list) -> str:
    if name in compare_list:
        for i in range(len(compare_list)):
            if "." in name:
                if f"{'.'.join(name.split('.')[:-1])} {i+1}.{name.split('.')[-1]}" not in compare_list:
                    name = f"{'.'.join(name.split('.')[:-1])} {i+1}.{name.split('.')[-1]}"
                    break
            else:
                if f"{name} {i+1}" not in compare_list:
                    name = f"{name} {i+1}"
                    break
    return name

class instance:

    def __init__(self, sql_path:str):
        self.sql_path = sql_path
        if os.path.exists(os.path.join(data_dir, "chats_test.db")) and not os.path.exists(os.path.join(data_dir, "alpaca.db")):
            shutil.move(os.path.join(data_dir, "chats_test.db"), os.path.join(data_dir, "alpaca.db"))
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()

        tables = {
            "chat": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "name": "TEXT NOT NULL"
            },
            "message": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "chat_id": "TEXT NOT NULL",
                "role": "TEXT NOT NULL",
                "model": "TEXT",
                "date_time": "DATETIME NOT NULL",
                "content": "TEXT NOT NULL"
            },
            "attachment": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "message_id": "TEXT NOT NULL",
                "type": "TEXT NOT NULL",
                "name": "TEXT NOT NULL",
                "content": "TEXT NOT NULL"
            },
            "model": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "picture": "TEXT NOT NULL"
            },
            "preferences": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "value": "TEXT",
                "type": "TEXT"
            },
            "instances": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "name": "TEXT NOT NULL",
                "type": "TEXT NOT NULL",
                "url": "TEXT",
                "max_tokens": "INTEGER NOT NULL",
                "api": "TEXT",
                "temperature": "REAL NOT NULL",
                "seed": "INTEGER NOT NULL",
                "overrides": "TEXT NOT NULL",
                "default_model": "TEXT",
                "title_model": "TEXT",
                "model_directory": "TEXT",
                "pinned": "INTEGER NOT NULL"
            }
        }

        for table_name, columns in tables.items():
            columns_def = ", ".join([f"{col_name} {col_def}" for col_name, col_def in columns.items()])
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_def})")

        # Ollama is available but there are no instances added
        if len(self.get_instances()) == 0 and shutil.which('ollama'):
            overrides = {
                'HSA_OVERRIDE_GFX_VERSION': '',
                'CUDA_VISIBLE_DEVICES': '',
                'ROCR_VISIBLE_DEVICES': ''
            }
            self.insert_or_update_instance(instance_manager.ollama_managed(generate_uuid(), 'Alpaca', 'http://0.0.0.0:11435', 0.7, 0, overrides, os.path.join(data_dir, '.ollama', 'models'), None, None, True))

        if self.get_preference('run_remote'):
            self.insert_or_update_instance(instance_manager.ollama(generate_uuid(), _('Legacy Remote Instance'), self.get_preference('remote_url'), self.get_preference('remote_bearer_token'), 0.7, 0, None, None, False))

        # Remove stuff from previous versions (cleaning)
        try:
            cursor.execute("DELETE FROM preferences WHERE id IN ('default_model', 'local_port', 'remote_url', 'remote_bearer_token', 'run_remote', 'idle_timer', 'model_directory', 'temperature', 'seed', 'keep_alive', 'show_welcome_dialog')")
            cursor.execute("DROP TABLE overrides")
        except Exception as e:
            pass
        sqlite_con.commit()
        sqlite_con.close()

    ###########
    ## CHATS ##
    ###########

    def get_chats(self) -> list:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        chats = cursor.execute('SELECT chat.id, chat.name, MAX(message.date_time) AS latest_message_time FROM chat LEFT JOIN message ON chat.id = message.chat_id GROUP BY chat.id ORDER BY latest_message_time DESC').fetchall()
        sqlite_con.close()
        return chats

    def get_messages(self, chat) -> list:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        messages = cursor.execute("SELECT id, role, model, date_time, content FROM message WHERE chat_id=?", (chat.chat_id,)).fetchall()
        sqlite_con.close()
        return messages

    def get_attachments(self, message) -> list:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        attachments = cursor.execute("SELECT id, type, name, content FROM attachment WHERE message_id=?", (message.message_id,)).fetchall()
        sqlite_con.close()
        return attachments

    def export_db(self, chat, export_sql_path:str) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("ATTACH DATABASE ? AS export", (export_sql_path,))
        cursor.execute("CREATE TABLE export.chat AS SELECT * FROM chat WHERE id=?", (chat.chat_id,))
        cursor.execute("CREATE TABLE export.message AS SELECT * FROM message WHERE chat_id=?", (chat.chat_id,))
        cursor.execute("CREATE TABLE export.attachment AS SELECT a.* FROM attachment as a JOIN message m ON a.message_id = m.id WHERE m.chat_id=?", (chat.chat_id,))
        sqlite_con.commit()
        sqlite_con.close()

    def insert_or_update_chat(self, chat) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        if cursor.execute("SELECT id FROM chat WHERE id=?", (chat.chat_id,)).fetchone():
            cursor.execute("UPDATE chat SET name=? WHERE id=?", (chat.get_name(), chat.chat_id))
        else:
            cursor.execute("INSERT INTO chat (id, name) VALUES (?, ?)", (chat.chat_id, chat.get_name()))
        sqlite_con.commit()
        sqlite_con.close()

    def delete_chat(self, chat) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("DELETE FROM chat WHERE id=?", (chat.chat_id,))
        for message in cursor.execute("SELECT id FROM message WHERE chat_id=?", (chat.chat_id,)).fetchall():
            cursor.execute("DELETE FROM attachment WHERE message_id=?", (message[0],))
        cursor.execute("DELETE FROM message WHERE chat_id=?", (chat.chat_id,))
        sqlite_con.commit()
        sqlite_con.close()

    def duplicate_chat(self, old_chat, new_chat) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("INSERT INTO chat (id, name) VALUES (?, ?)", (new_chat.chat_id, new_chat.get_name()))
        for message in cursor.execute("SELECT id, role, model, date_time, content FROM message WHERE chat_id=?", (old_chat.chat_id,)).fetchall():
            new_message_id = generate_uuid()
            cursor.execute("INSERT INTO message (id, chat_id, role, model, date_time, content) VALUES (?, ?, ?, ?, ?, ?)",
                (new_message_id, new_chat.chat_id, message[1], message[2], message[3], message[4]))
            for attachment in cursor.execute("SELECT type, name, content FROM attachment WHERE message_id=?", (message[0],)).fetchall():
                cursor.execute("INSERT INTO attachment (id, message_id, type, name, content) VALUES (?, ?, ?, ?, ?)",
                    (generate_uuid(), new_message_id, attachment[0], attachment[1], attachment[2]))
        sqlite_con.commit()
        sqlite_con.close()

    def import_chat(self, import_sql_path:str, chat_names:list) -> list:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("ATTACH DATABASE ? AS import", (import_sql_path,))
        chat_widgets = []
        # Check repeated chat.name
        for repeated_chat in cursor.execute("SELECT import.chat.id, import.chat.name FROM import.chat JOIN chat dbchat ON import.chat.name = dbchat.name").fetchall():
            new_name = generate_numbered_name(repeated_chat[1], chat_names)
            cursor.execute("UPDATE import.chat SET name=? WHERE id=?", (new_name, repeated_chat[0]))
        # Check repeated chat.id
        for repeated_chat in cursor.execute("SELECT import.chat.id FROM import.chat JOIN chat dbchat ON import.chat.id = dbchat.id").fetchall():
            new_id = generate_uuid()
            cursor.execute("UPDATE import.chat SET id=? WHERE id=?", (new_id, repeated_chat[0]))
            cursor.execute("UPDATE import.message SET chat_id=? WHERE chat_id=?", (new_id, repeated_chat[0]))
        # Check repeated message.id
        for repeated_message in cursor.execute("SELECT import.message.id FROM import.message JOIN message dbmessage ON import.message.id = dbmessage.id").fetchall():
            new_id = generate_uuid()
            cursor.execute("UPDATE import.attachment SET message_id=? WHERE message_id=?", (new_id, repeated_message[0]))
            cursor.execute("UPDATE import.message SET id=? WHERE id=?", (new_id, repeated_message[0]))
        # Check repeated attachment.id
        for repeated_attachment in cursor.execute("SELECT import.attachment.id FROM import.attachment JOIN attachment dbattachment ON import.attachment.id = dbattachment.id").fetchall():
            new_id = generate_uuid()
            cursor.execute("UPDATE import.attachment SET id=? WHERE id=?", (new_id, repeated_attachment[0]))
        # Import
        cursor.execute("INSERT INTO chat SELECT * FROM import.chat")
        cursor.execute("INSERT INTO message SELECT * FROM import.message")
        cursor.execute("INSERT INTO attachment SELECT * FROM import.attachment")
        new_chats = cursor.execute("SELECT * FROM import.chat").fetchall()
        sqlite_con.commit()
        sqlite_con.close()
        return new_chats

    ##############
    ## MESSAGES ##
    ##############

    def insert_or_update_message(self, message, force_chat_id:str=None) -> None:
        message_author = 'user'
        if message.bot:
            message_author = 'assistant'
        if message.system:
            message_author = 'system'
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        if cursor.execute("SELECT id FROM message WHERE id=?", (message.message_id,)).fetchone():
            cursor.execute("UPDATE message SET chat_id=?, role=?, model=?, date_time=?, content=? WHERE id=?",
            (force_chat_id if force_chat_id else message.get_chat().chat_id, message_author, message.model, message.dt.strftime("%Y/%m/%d %H:%M:%S"), message.text if message.text else '', message.message_id))
        else:
            cursor.execute("INSERT INTO message (id, chat_id, role, model, date_time, content) VALUES (?, ?, ?, ?, ?, ?)",
            (message.message_id, force_chat_id if force_chat_id else message.get_chat().chat_id, message_author, message.model, message.dt.strftime("%Y/%m/%d %H:%M:%S"), message.text if message.text else ''))
        sqlite_con.commit()
        sqlite_con.close()

    def delete_message(self, message) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("DELETE FROM message WHERE id=?", (message.message_id,))
        cursor.execute("DELETE FROM attachment WHERE message_id=?", (message.message_id,))
        sqlite_con.commit()
        sqlite_con.close()

    def add_attachment(self, message, attachment) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("INSERT INTO attachment (id, message_id, type, name, content) VALUES (?, ?, ?, ?, ?)",
        (generate_uuid(), message.message_id, attachment.file_type, attachment.get_name(), attachment.file_content))
        sqlite_con.commit()
        sqlite_con.close()

    #################
    ## PREFERENCES ##
    #################

    def insert_or_update_preferences(self, preferences:dict) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        for preference_id, preference_value in preferences.items():
            if cursor.execute("SELECT id FROM preferences WHERE id=?", (preference_id,)).fetchone():
                cursor.execute("UPDATE preferences SET value=?, type=? WHERE id=?", (preference_value, str(type(preference_value)), preference_id))
            else:
                cursor.execute("INSERT INTO preferences (id, value, type) VALUES (?, ?, ?)", (preference_id, preference_value, str(type(preference_value))))
        sqlite_con.commit()
        sqlite_con.close()

    def get_preference(self, preference_name:str, default=None) -> object:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        result = cursor.execute("SELECT value, type FROM preferences WHERE id=?", (preference_name,)).fetchone()
        sqlite_con.close()
        if result:
            type_map = {
                "<class 'int'>": int,
                "<class 'float'>": float,
                "<class 'bool'>": lambda x: x == "1"
            }
            if result[1] in type_map:
                return type_map[result[1]](result[0])
            else:
                return result[0]
        else:
            return default

    def get_preferences(self) -> dict:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        result = cursor.execute("SELECT id, value, type FROM preferences").fetchall()
        sqlite_con.close()
        preferences = {}
        type_map = {
            "<class 'int'>": int,
            "<class 'float'>": float,
            "<class 'bool'>": lambda x: x == "1"
        }
        for row in result:
            value = row[1]
            if row[2] in type_map:
                value = type_map[row[2]](value)
            preferences[row[0]] = value
        return preferences

    ###########
    ## MODEL ##
    ###########

    def insert_or_update_model_picture(self, model_id:str, picture_content:str) -> None:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        if cursor.execute("SELECT id FROM model WHERE id=?", (model_id,)).fetchone():
            cursor.execute("UPDATE model SET picture=? WHERE id=?", (picture_content, model_id))
        else:
            cursor.execute("INSERT INTO model (id, picture) VALUES (?, ?)", (model_id, picture_content))
        sqlite_con.commit()
        sqlite_con.close()

    def get_model_picture(self, model_id:str) -> str:
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        res = cursor.execute("SELECT picture FROM model WHERE id=?", (model_id,)).fetchone()
        sqlite_con.close()
        if res:
            return res[0]

    def delete_model_picture(self, model_id:str):
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("DELETE FROM model WHERE id=?", (model_id,))
        sqlite_con.commit()
        sqlite_con.close()

    ##############
    ## OVERRIDE ##
    ##############

    def insert_or_update_override(self, override_id:str, override_value:str):
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        if cursor.execute("SELECT id FROM overrides WHERE id=?", (override_id,)).fetchone():
            cursor.execute("UPDATE overrides SET value=? WHERE id=?", (override_value, override_id))
        else:
            cursor.execute("INSERT INTO overrides (id, value) VALUES (?, ?)", (override_id, override_value))
        sqlite_con.commit()
        sqlite_con.close()

    def get_overrides(self):
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        result = cursor.execute("SELECT id, value FROM overrides").fetchall()
        sqlite_con.close()
        overrides = {}
        for row in result:
            overrides[row[0]] = row[1]
        return overrides

    ###############
    ## Instances ##
    ###############

    def get_instances(self) -> list:
        columns = ['id', 'name', 'type', 'url', 'max_tokens', 'api', 'temperature', 'seed', 'overrides', 'model_directory', 'default_model', 'title_model', 'pinned']
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        result = cursor.execute("SELECT {} FROM instances".format(', '.join(columns))).fetchall()
        sqlite_con.close()
        instances = []
        for row in result:
            instances.append({})
            for i, column in enumerate(columns):
                value = row[i]
                if column == 'overrides':
                    try:
                        value = json.loads(value)
                    except Exception as e:
                        value = {}
                elif column == 'pinned':
                    value = value == 1
                instances[-1][column] = value
        return instances

    def insert_or_update_instance(self, ins):
        data = {
            'id': ins.instance_id,
            'name': ins.name,
            'type': ins.instance_type,
            'url': ins.instance_url,
            'max_tokens': ins.max_tokens,
            'api': ins.api_key,
            'temperature': ins.temperature,
            'seed': ins.seed,
            'overrides': json.dumps(ins.overrides),
            'model_directory': ins.model_directory,
            'default_model': ins.default_model,
            'title_model': ins.title_model,
            'pinned': ins.pinned
        }

        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        if cursor.execute("SELECT id FROM instances WHERE id=?", (data.get('id'),)).fetchone():
            instance_id = data.pop('id', None)
            set_clause = ', '.join(f"{key} = ?" for key in data.keys())
            values = list(data.values()) + [instance_id]
            cursor.execute(f"UPDATE instances SET {set_clause} WHERE id=?", values)
        else:
            columns = ', '.join(data.keys())
            placeholders = ', '.join('?' for _ in data)
            values = tuple(data.values())
            cursor.execute(f'INSERT INTO instances ({columns}) VALUES ({placeholders})', values)
        sqlite_con.commit()
        sqlite_con.close()

    def delete_instance(self, instance_id:str):
        sqlite_con = sqlite3.connect(self.sql_path)
        cursor = sqlite_con.cursor()
        cursor.execute("DELETE FROM instances WHERE id=?", (instance_id,))
        sqlite_con.commit()
        sqlite_con.close()
