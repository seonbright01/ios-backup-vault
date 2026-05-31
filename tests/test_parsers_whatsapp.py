import sqlite3
from pathlib import Path
from ios_backup_vault.parsers.whatsapp import parse_whatsapp


def _make(path: Path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE ZWACHATSESSION (Z_PK INTEGER PRIMARY KEY, ZPARTNERNAME TEXT, ZCONTACTJID TEXT);
        CREATE TABLE ZWAMESSAGE (Z_PK INTEGER PRIMARY KEY, ZTEXT TEXT, ZMESSAGEDATE REAL,
            ZISFROMME INTEGER, ZCHATSESSION INTEGER);
        INSERT INTO ZWACHATSESSION VALUES (1,'Bob','11@s.whatsapp.net');
        INSERT INTO ZWAMESSAGE VALUES (1,'hi',599558400.0,0,1);
        INSERT INTO ZWAMESSAGE VALUES (2,'yo',599558460.0,1,1);
        """
    )
    con.commit(); con.close()


def test_parse_whatsapp(tmp_path):
    db = tmp_path / "ChatStorage.sqlite"; _make(db)
    convos = parse_whatsapp(str(db))
    assert len(convos) == 1
    c = convos[0]
    assert c["name"] == "Bob"
    assert [m["text"] for m in c["messages"]] == ["hi", "yo"]
    assert [m["is_from_me"] for m in c["messages"]] == [False, True]
    assert c["messages"][0]["timestamp"].startswith("2020-01-01")
