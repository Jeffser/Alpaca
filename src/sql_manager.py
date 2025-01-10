# sql_manager.py

import sqlite3, uuid, datetime, os
from .internal import data_dir

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
            "overrides": {
                "id": "TEXT NOT NULL PRIMARY KEY",
                "value": "TEXT"
            }
        }

        for table_name, columns in tables.items():
            columns_def = ", ".join([f"{col_name} {col_def}" for col_name, col_def in columns.items()])
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_def})")
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
            (message.get_chat().chat_id, message_author, message.model, message.dt.strftime("%Y/%m/%d %H:%M:%S"), message.text if message.text else '', message.message_id))
        else:
            cursor.execute("INSERT INTO message (id, chat_id, role, model, date_time, content) VALUES (?, ?, ?, ?, ?, ?)",
            (message.message_id, message.get_chat().chat_id, message_author, message.model, message.dt.strftime("%Y/%m/%d %H:%M:%S"), message.text if message.text else ''))
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
                cursor.execute("INSERT INTO preferences (id, value, type) VALUES (?, ?)", (preference_id, preference_value, str(type(preference_value))))
        sqlite_con.commit()
        sqlite_con.close()

    def get_preference(self, preference_name:str) -> object:
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
