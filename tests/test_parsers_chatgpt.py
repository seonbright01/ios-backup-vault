from ios_backup_vault.parsers.chatgpt import parse_chatgpt


def test_parse_chatgpt():
    data = {
        "title": "Hello chat",
        "creation_date": 1700000000.0,
        "tree": {"storage": [
            "id1", {"content": {"author": {"role": "user"},
                                "content": {"content_type": "text", "parts": ["hi there"]},
                                "create_time": 1700000000.0}},
            "id2", {"content": {"author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["hello!"]},
                                "create_time": 1700000001.0}},
            "id3", {"content": {"author": {"role": "system"},
                                "content": {"content_type": "model_editable_context", "model_set_context": ""},
                                "create_time": 1699999999.0}},
        ]},
    }
    c = parse_chatgpt(data)
    assert c["title"] == "Hello chat"
    assert [m["role"] for m in c["messages"]] == ["user", "assistant"]
    assert [m["text"] for m in c["messages"]] == ["hi there", "hello!"]
    assert c["messages"][0]["timestamp"].startswith("2023-11")
    assert c["created"].startswith("2023-11")
