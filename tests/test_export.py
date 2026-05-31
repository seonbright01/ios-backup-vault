import csv
import io
import json

from ios_backup_vault.parsers.export import serialize


_ITEMS = {
    "messages": [
        {"name": "홍길동", "chat_identifier": "+8210",
         "messages": [{"text": "hi <b>", "timestamp": "2024-01-01", "is_from_me": True},
                      {"text": "bye", "timestamp": "2024-01-02", "is_from_me": False}]},
    ],
    "contacts": [{"name": "김철수", "values": ["010", "0101"]}],
}


def test_json():
    out = serialize(_ITEMS, "json")
    assert "export.json" in out
    assert json.loads(out["export.json"].decode("utf-8")) == _ITEMS


def test_txt():
    out = serialize(_ITEMS, "txt")
    text = out["export.txt"].decode("utf-8")
    assert "hi <b>" in text
    assert "홍길동" in text
    assert "+8210" in text  # 대화 식별자(번호)도 함께 나가야 함


def test_html():
    out = serialize(_ITEMS, "html")
    html = out["export.html"].decode("utf-8")
    assert "&lt;b&gt;" in html
    assert "<b>" not in html.split("<style")[-1] or "hi <b>" not in html


def test_csv():
    out = serialize(_ITEMS, "csv")
    assert "messages.csv" in out
    assert "contacts.csv" in out
    text = out["messages.csv"].decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["conversation", "chat_identifier", "is_from_me", "timestamp", "text"]
    assert any("hi <b>" in r for r in rows)
    # chat_identifier "+8210"은 수식 살균으로 "'+8210"이 되므로 substring으로 확인
    assert any("+8210" in c for r in rows for c in r)
    # empty category -> no file
    out2 = serialize({"messages": []}, "csv")
    assert "messages.csv" not in out2


def test_csv_formula_injection_sanitized():
    items = {"contacts": [{"name": "=cmd|'/c calc'", "values": ["+15551234"]}]}
    out = serialize(items, "csv")
    text = out["contacts.csv"].decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    # 수식 트리거 문자로 시작하던 셀은 ' 가 앞에 붙어 무력화
    assert any(cell.startswith("'=") for r in rows for cell in r)
    assert not any(cell.startswith("=cmd") for r in rows for cell in r)


def test_unknown_fmt():
    try:
        serialize(_ITEMS, "pdf")
        assert False, "expected ValueError"
    except ValueError:
        pass
