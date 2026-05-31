import sqlite3
from pathlib import Path
from ios_backup_vault.parsers.messages import parse_messages, mac_time_to_iso


def _make_sms_db(path: Path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT, attributedBody BLOB,
            handle_id INTEGER, date INTEGER, is_from_me INTEGER);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT, display_name TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        INSERT INTO handle VALUES (1, '+1234');
        INSERT INTO chat VALUES (1, '+1234', '');
        INSERT INTO message VALUES (1, 'Hello', NULL, 1, 599558400000000000, 0);
        INSERT INTO message VALUES (2, 'Hi back', NULL, 1, 599558460000000000, 1);
        INSERT INTO chat_message_join VALUES (1,1),(1,2);
        """
    )
    con.commit(); con.close()


def test_mac_time_ns_to_iso():
    assert mac_time_to_iso(599558400000000000).startswith("2020-01-01")


def test_parse_messages_groups_by_chat(tmp_path):
    db = tmp_path / "sms.db"; _make_sms_db(db)
    convos = parse_messages(str(db))
    assert len(convos) == 1
    c = convos[0]
    assert c["chat_identifier"] == "+1234"
    assert [m["text"] for m in c["messages"]] == ["Hello", "Hi back"]
    assert [m["is_from_me"] for m in c["messages"]] == [False, True]
    assert c["messages"][0]["timestamp"].startswith("2020-01-01")
