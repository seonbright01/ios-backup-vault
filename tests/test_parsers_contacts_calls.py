import sqlite3
from pathlib import Path
from ios_backup_vault.parsers.contacts import parse_contacts
from ios_backup_vault.parsers.calls import parse_calls


def _make_addressbook(path: Path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE ABPerson (ROWID INTEGER PRIMARY KEY, First TEXT, Last TEXT);
        CREATE TABLE ABMultiValue (UID INTEGER PRIMARY KEY, record_id INTEGER, value TEXT);
        INSERT INTO ABPerson VALUES (1,'Ada','Lovelace');
        INSERT INTO ABMultiValue VALUES (1,1,'+100');
        INSERT INTO ABMultiValue VALUES (2,1,'ada@x.com');
        """
    )
    con.commit(); con.close()


def _make_callhistory(path: Path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE ZCALLRECORD (Z_PK INTEGER PRIMARY KEY, ZADDRESS TEXT,
            ZDATE REAL, ZDURATION REAL, ZORIGINATED INTEGER);
        INSERT INTO ZCALLRECORD VALUES (1,'+100', 599558400.0, 65.0, 1);
        """
    )
    con.commit(); con.close()


def test_parse_contacts(tmp_path):
    db = tmp_path / "ab.sqlitedb"; _make_addressbook(db)
    people = parse_contacts(str(db))
    assert len(people) == 1
    assert people[0]["name"] == "Ada Lovelace"
    assert "+100" in people[0]["values"] and "ada@x.com" in people[0]["values"]


def test_parse_calls(tmp_path):
    db = tmp_path / "ch.storedata"; _make_callhistory(db)
    calls = parse_calls(str(db))
    assert len(calls) == 1
    assert calls[0]["address"] == "+100"
    assert calls[0]["duration_sec"] == 65
    assert calls[0]["originated"] is True
    assert calls[0]["timestamp"].startswith("2020-01-01")
