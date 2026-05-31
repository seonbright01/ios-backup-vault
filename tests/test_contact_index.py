from ios_backup_vault.parsers.contacts import normalize_value, build_contact_index, resolve_name


def test_normalize_phone_last8():
    assert normalize_value("+82 10-1234-5678") == "12345678"
    assert normalize_value("010-1234-5678") == "12345678"


def test_normalize_email_lower():
    assert normalize_value("Ada@X.com") == "ada@x.com"


def test_build_and_resolve():
    contacts = [{"name": "Ada", "values": ["+82 10-1234-5678", "ada@x.com"]}]
    idx = build_contact_index(contacts)
    assert resolve_name(idx, "01012345678") == "Ada"
    assert resolve_name(idx, "ADA@x.com") == "Ada"
    assert resolve_name(idx, "+1 999 0000") is None
    assert resolve_name(idx, "") is None
