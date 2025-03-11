"""
This file manages the SQLite saving system backing Alpaca; it's responsible
for storing chats, instances, preferences and more.
"""

# sql_manager.py

from typing import Union
import sqlite3
import uuid
import datetime
import os
import shutil
import json
import sys

from .internal import data_dir
from . import instance_manager


def generate_timestamped_uuid() -> str:
    """
    Returns a new, randomly generated UUID together with a timestamp.
    """

    return f"{datetime.datetime.today().strftime('%Y%m%d%H%M%S%f')}{uuid.uuid4().hex}"


def generate_numbered_name(name: str, compare_list: "list[str]") -> str:
    """
    Generates a numbered name from two parameters, the name and a list to
    compare it to. If the name of the chat already exists in our compare list,
    we number it to make it distinctive of the original.
    """

    if name in compare_list:
        for i in range(1, len(compare_list) + 1):
            if "." in name:
                if (
                    f"{'.'.join(name.split('.')[:-1])} {i}.{name.split('.')[-1]}"
                    not in compare_list
                ):
                    name = f"{'.'.join(name.split('.')[:-1])} {i}.{name.split('.')[-1]}"
                    break
            else:
                if f"{name} {i}" not in compare_list:
                    name = f"{name} {i}"
                    break
    return name


class SQLiteConnection:
    """
    This class manages the context for SQLite database connections.
    """

    def __init__(self, sql_path: str) -> None:
        """
        We define ourselves three attributes - a path for the database file, a
        connection and a cursor instance. The two latter ones can be None if
        the context is not entered yet.
        """

        self.sql_path: str = sql_path
        self.sqlite_con: "Union[sqlite3.Connection, None]" = None
        self.cursor: "Union[sqlite3.Cursor, None]" = None

    def __enter__(self):
        """
        What happens when the context is entered - in this case, establish a
        connection to the database.
        """

        self.sqlite_con = sqlite3.connect(self.sql_path)
        self.cursor = self.sqlite_con.cursor()

        return self

    def __exit__(self, exception_type, exception_val, traceback) -> None:
        """
        What to do once the context is exited again: commit and close the
        connection.
        """

        if self.sqlite_con.in_transaction:
            self.sqlite_con.commit()

        self.sqlite_con.close()


class Instance:
    """
    An instance class for the SQLite database used by Alpaca - it can be used
    to interface with the database in a modular and extensible way.
    """

    def __init__(self, sql_path: str):
        self.sql_path = sql_path

        if os.path.exists(os.path.join(data_dir, "chats_test.db")) and not os.path.exists(os.path.join(data_dir, "alpaca.db")):
            shutil.move(os.path.join(data_dir, "chats_test.db"), os.path.join(data_dir, "alpaca.db"))

        with SQLiteConnection(self.sql_path) as c:
            tables = {
                "chat": {
                    "id": "TEXT NOT NULL PRIMARY KEY",
                    "name": "TEXT NOT NULL",
                },
                "message": {
                    "id": "TEXT NOT NULL PRIMARY KEY",
                    "chat_id": "TEXT NOT NULL",
                    "role": "TEXT NOT NULL",
                    "model": "TEXT",
                    "date_time": "DATETIME NOT NULL",
                    "content": "TEXT NOT NULL",
                },
                "attachment": {
                    "id": "TEXT NOT NULL PRIMARY KEY",
                    "message_id": "TEXT NOT NULL",
                    "type": "TEXT NOT NULL",
                    "name": "TEXT NOT NULL",
                    "content": "TEXT NOT NULL",
                },
                "model": {
                    "id": "TEXT NOT NULL PRIMARY KEY",
                    "picture": "TEXT NOT NULL",
                },
                "preferences": {
                    "id": "TEXT NOT NULL PRIMARY KEY",
                    "value": "TEXT",
                    "type": "TEXT",
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
                    "pinned": "INTEGER NOT NULL",
                },
            }

            for table_name, columns in tables.items():
                columns_def = ", ".join([f"{col_name} {col_def}" for col_name, col_def in columns.items()])
                c.cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_def})")

            # Ollama is available but there are no instances added
            if len(self.get_instances()) == 0 and shutil.which("ollama"):
                overrides = {
                    "HSA_OVERRIDE_GFX_VERSION": "",
                    "CUDA_VISIBLE_DEVICES": "",
                    "ROCR_VISIBLE_DEVICES": "",
                }
                self.insert_or_update_instance(
                    instance_manager.ollama_managed(
                        generate_timestamped_uuid(),
                        "Alpaca",
                        "http://{}:11435".format("127.0.0.1" if sys.platform == "win32" else "0.0.0.0"),
                        0.7,
                        0,
                        overrides,
                        os.path.join(data_dir, ".ollama", "models"),
                        None,
                        None,
                        True,
                    )
                )

            if self.get_preference("run_remote"):
                self.insert_or_update_instance(
                    instance_manager.ollama(
                        generate_timestamped_uuid(),
                        _("Legacy Remote Instance"),
                        self.get_preference("remote_url"),
                        self.get_preference("remote_bearer_token"),
                        0.7,
                        0,
                        None,
                        None,
                        False,
                    )
                )

            # Remove stuff from previous versions (cleaning)
            try:
                c.cursor.execute(
                    "DELETE FROM preferences WHERE id IN ('default_model', \
                    'local_port', 'remote_url', 'remote_bearer_token', 'run_remote', \
                    'idle_timer', 'model_directory', 'temperature', 'seed', 'keep_alive', \
                    'show_welcome_dialog')"
                )
                c.cursor.execute("DROP TABLE overrides")
            except Exception:
                pass

    ###########
    ## CHATS ##
    ###########

    def get_chats(self) -> list:
        with SQLiteConnection(self.sql_path) as c:
            chats = c.cursor.execute(
                "SELECT chat.id, chat.name, MAX(message.date_time) AS \
                latest_message_time FROM chat LEFT JOIN message ON chat.id = message.chat_id \
                GROUP BY chat.id ORDER BY latest_message_time DESC"
            ).fetchall()

        return chats

    def get_messages(self, chat) -> list:
        with SQLiteConnection(self.sql_path) as c:
            messages = c.cursor.execute(
                "SELECT id, role, model, date_time, content FROM message WHERE chat_id=?",
                (chat.chat_id,),
            ).fetchall()

        return messages

    def get_attachments(self, message) -> list:
        with SQLiteConnection(self.sql_path) as c:
            attachments = c.cursor.execute(
                "SELECT id, type, name, content FROM attachment WHERE message_id=?",
                (message.message_id,),
            ).fetchall()

        return attachments

    def export_db(self, chat, export_sql_path: str) -> None:
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute("ATTACH DATABASE ? AS export", (export_sql_path,))
            c.cursor.execute(
                "CREATE TABLE export.chat AS SELECT * FROM chat WHERE id=?",
                (chat.chat_id,),
            )
            c.cursor.execute(
                "CREATE TABLE export.message AS SELECT * FROM message WHERE chat_id=?",
                (chat.chat_id,),
            )
            c.cursor.execute(
                "CREATE TABLE export.attachment AS SELECT a.* FROM attachment as a JOIN message m ON a.message_id = m.id WHERE m.chat_id=?",
                (chat.chat_id,),
            )

    def insert_or_update_chat(self, chat) -> None:
        with SQLiteConnection(self.sql_path) as c:
            if c.cursor.execute(
                "SELECT id FROM chat WHERE id=?", (chat.chat_id,)
            ).fetchone():
                c.cursor.execute(
                    "UPDATE chat SET name=? WHERE id=?",
                    (chat.get_name(), chat.chat_id),
                )
            else:
                c.cursor.execute(
                    "INSERT INTO chat (id, name) VALUES (?, ?)",
                    (chat.chat_id, chat.get_name()),
                )

    def delete_chat(self, chat) -> None:
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute("DELETE FROM chat WHERE id=?", (chat.chat_id,))

            for message in c.cursor.execute(
                "SELECT id FROM message WHERE chat_id=?", (chat.chat_id,)
            ).fetchall():
                c.cursor.execute(
                    "DELETE FROM attachment WHERE message_id=?", (message[0],)
                )

            c.cursor.execute(
                "DELETE FROM message WHERE chat_id=?", (chat.chat_id,)
            )

    def duplicate_chat(self, old_chat, new_chat) -> None:
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute(
                "INSERT INTO chat (id, name) VALUES (?, ?)",
                (new_chat.chat_id, new_chat.get_name()),
            )

            for message in c.cursor.execute(
                "SELECT id, role, model, date_time, content FROM message WHERE chat_id=?",
                (old_chat.chat_id,),
            ).fetchall():
                new_message_id = generate_timestamped_uuid()

                c.cursor.execute(
                    "INSERT INTO message (id, chat_id, role, model, date_time, content) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        new_message_id,
                        new_chat.chat_id,
                        message[1],
                        message[2],
                        message[3],
                        message[4],
                    ),
                )

                for attachment in c.cursor.execute(
                    "SELECT type, name, content FROM attachment WHERE message_id=?",
                    (message[0],),
                ).fetchall():
                    c.cursor.execute(
                        "INSERT INTO attachment (id, message_id, type, name, content) VALUES (?, ?, ?, ?, ?)",
                        (
                            generate_timestamped_uuid(),
                            new_message_id,
                            attachment[0],
                            attachment[1],
                            attachment[2],
                        ),
                    )

    def import_chat(self, import_sql_path: str, chat_names: list) -> list:
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute("ATTACH DATABASE ? AS import", (import_sql_path,))
            _chat_widgets = []

            # Check repeated chat.name
            for repeated_chat in c.cursor.execute(
                "SELECT import.chat.id, import.chat.name FROM import.chat JOIN chat dbchat ON import.chat.name = dbchat.name"
            ).fetchall():
                new_name = generate_numbered_name(repeated_chat[1], chat_names)

                c.cursor.execute(
                    "UPDATE import.chat SET name=? WHERE id=?",
                    (new_name, repeated_chat[0]),
                )

            # Check repeated chat.id
            for repeated_chat in c.cursor.execute(
                "SELECT import.chat.id FROM import.chat JOIN chat dbchat ON import.chat.id = dbchat.id"
            ).fetchall():
                new_id = generate_timestamped_uuid()

                c.cursor.execute(
                    "UPDATE import.chat SET id=? WHERE id=?",
                    (new_id, repeated_chat[0]),
                )
                c.cursor.execute(
                    "UPDATE import.message SET chat_id=? WHERE chat_id=?",
                    (new_id, repeated_chat[0]),
                )

            # Check repeated message.id
            for repeated_message in c.cursor.execute(
                "SELECT import.message.id FROM import.message JOIN message dbmessage ON import.message.id = dbmessage.id"
            ).fetchall():
                new_id = generate_timestamped_uuid()

                c.cursor.execute(
                    "UPDATE import.attachment SET message_id=? WHERE message_id=?",
                    (new_id, repeated_message[0]),
                )
                c.cursor.execute(
                    "UPDATE import.message SET id=? WHERE id=?",
                    (new_id, repeated_message[0]),
                )

            # Check repeated attachment.id
            for repeated_attachment in c.cursor.execute(
                "SELECT import.attachment.id FROM import.attachment JOIN attachment dbattachment ON import.attachment.id = dbattachment.id"
            ).fetchall():
                new_id = generate_timestamped_uuid()

                c.cursor.execute(
                    "UPDATE import.attachment SET id=? WHERE id=?",
                    (new_id, repeated_attachment[0]),
                )

            # Import
            c.cursor.execute("INSERT INTO chat SELECT * FROM import.chat")
            c.cursor.execute(
                "INSERT INTO message SELECT * FROM import.message"
            )
            c.cursor.execute(
                "INSERT INTO attachment SELECT * FROM import.attachment"
            )

            new_chats = c.cursor.execute(
                "SELECT * FROM import.chat"
            ).fetchall()

        return new_chats

    ##############
    ## MESSAGES ##
    ##############

    def insert_or_update_message(
        self, message, force_chat_id: str = None
    ) -> None:
        message_author = "user"
        if message.bot:
            message_author = "assistant"
        if message.system:
            message_author = "system"

        with SQLiteConnection(self.sql_path) as c:
            if c.cursor.execute(
                "SELECT id FROM message WHERE id=?", (message.message_id,)
            ).fetchone():
                c.cursor.execute(
                    "UPDATE message SET chat_id=?, role=?, model=?, date_time=?, content=? WHERE id=?",
                    (
                        (
                            force_chat_id
                            if force_chat_id
                            else message.get_chat().chat_id
                        ),
                        message_author,
                        message.model,
                        message.dt.strftime("%Y/%m/%d %H:%M:%S"),
                        message.text if message.text else "",
                        message.message_id,
                    ),
                )
            else:
                c.cursor.execute(
                    "INSERT INTO message (id, chat_id, role, model, date_time, content) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        message.message_id,
                        (
                            force_chat_id
                            if force_chat_id
                            else message.get_chat().chat_id
                        ),
                        message_author,
                        message.model,
                        message.dt.strftime("%Y/%m/%d %H:%M:%S"),
                        message.text if message.text else "",
                    ),
                )

    def delete_message(self, message) -> None:
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute(
                "DELETE FROM message WHERE id=?", (message.message_id,)
            )
            c.cursor.execute(
                "DELETE FROM attachment WHERE message_id=?",
                (message.message_id,),
            )

    def add_attachment(self, message, attachment) -> None:
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute(
                "INSERT INTO attachment (id, message_id, type, name, content) VALUES (?, ?, ?, ?, ?)",
                (
                    generate_timestamped_uuid(),
                    message.message_id,
                    attachment.file_type,
                    attachment.get_name(),
                    attachment.file_content,
                ),
            )

    #################
    ## PREFERENCES ##
    #################

    def insert_or_update_preferences(self, preferences: dict) -> None:
        with SQLiteConnection(self.sql_path) as c:
            for preference_id, preference_value in preferences.items():
                if c.cursor.execute(
                    "SELECT id FROM preferences WHERE id=?", (preference_id,)
                ).fetchone():
                    c.cursor.execute(
                        "UPDATE preferences SET value=?, type=? WHERE id=?",
                        (
                            preference_value,
                            str(type(preference_value)),
                            preference_id,
                        ),
                    )
                else:
                    c.cursor.execute(
                        "INSERT INTO preferences (id, value, type) VALUES (?, ?, ?)",
                        (
                            preference_id,
                            preference_value,
                            str(type(preference_value)),
                        ),
                    )

    def get_preference(self, preference_name: str, default=None) -> object:
        with SQLiteConnection(self.sql_path) as c:
            result = c.cursor.execute(
                "SELECT value, type FROM preferences WHERE id=?",
                (preference_name,),
            ).fetchone()

        if result:
            type_map = {
                "<class 'int'>": int,
                "<class 'float'>": float,
                "<class 'bool'>": lambda x: x == "1",
            }
            if result[1] in type_map:
                return type_map[result[1]](result[0])

            return result[0]

        return default

    def get_preferences(self) -> dict:
        with SQLiteConnection(self.sql_path) as c:
            result = c.cursor.execute(
                "SELECT id, value, type FROM preferences"
            ).fetchall()

        preferences = {}
        type_map = {
            "<class 'int'>": int,
            "<class 'float'>": float,
            "<class 'bool'>": lambda x: x == "1",
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

    def insert_or_update_model_picture(
        self, model_id: str, picture_content: str
    ) -> None:
        with SQLiteConnection(self.sql_path) as c:
            if c.cursor.execute(
                "SELECT id FROM model WHERE id=?", (model_id,)
            ).fetchone():
                c.cursor.execute(
                    "UPDATE model SET picture=? WHERE id=?",
                    (picture_content, model_id),
                )

            else:
                c.cursor.execute(
                    "INSERT INTO model (id, picture) VALUES (?, ?)",
                    (model_id, picture_content),
                )

    def get_model_picture(self, model_id: str) -> str:
        with SQLiteConnection(self.sql_path) as c:
            res = c.cursor.execute(
                "SELECT picture FROM model WHERE id=?", (model_id,)
            ).fetchone()

        return res[0] if res else None

    def delete_model_picture(self, model_id: str):
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute("DELETE FROM model WHERE id=?", (model_id,))

    ###############
    ## Instances ##
    ###############

    def get_instances(self) -> list:
        columns = [
            "id",
            "name",
            "type",
            "url",
            "max_tokens",
            "api",
            "temperature",
            "seed",
            "overrides",
            "model_directory",
            "default_model",
            "title_model",
            "pinned",
        ]

        with SQLiteConnection(self.sql_path) as c:
            result = c.cursor.execute(
                "SELECT {} FROM instances".format(", ".join(columns))
            ).fetchall()

        instances = []

        for row in result:
            instances.append({})

            for i, column in enumerate(columns):
                value = row[i]

                if column == "overrides":
                    try:
                        value = json.loads(value)
                    except Exception:
                        value = {}
                elif column == "pinned":
                    value = value == 1

                instances[-1][column] = value

        return instances

    def insert_or_update_instance(self, ins):
        data = {
            "id": ins.instance_id,
            "name": ins.name,
            "type": ins.instance_type,
            "url": ins.instance_url,
            "max_tokens": ins.max_tokens,
            "api": ins.api_key,
            "temperature": ins.temperature,
            "seed": ins.seed,
            "overrides": json.dumps(ins.overrides),
            "model_directory": ins.model_directory,
            "default_model": ins.default_model,
            "title_model": ins.title_model,
            "pinned": ins.pinned,
        }

        with SQLiteConnection(self.sql_path) as c:
            if c.cursor.execute(
                "SELECT id FROM instances WHERE id=?", (data.get("id"),)
            ).fetchone():
                instance_id = data.pop("id", None)
                set_clause = ", ".join(f"{key} = ?" for key in data)
                values = list(data.values()) + [instance_id]

                c.cursor.execute(
                    f"UPDATE instances SET {set_clause} WHERE id=?", values
                )
            else:
                columns = ", ".join(data.keys())
                placeholders = ", ".join("?" for _ in data)
                values = tuple(data.values())

                c.cursor.execute(
                    f"INSERT INTO instances ({columns}) VALUES ({placeholders})",
                    values,
                )

    def delete_instance(self, instance_id: str):
        with SQLiteConnection(self.sql_path) as c:
            c.cursor.execute(
                "DELETE FROM instances WHERE id=?", (instance_id,)
            )
