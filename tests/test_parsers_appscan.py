from ios_backup_vault.parsers.appscan import summarize_apps


def test_summarize_detects_messengers():
    rows = [
        ("f1", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "ChatStorage.sqlite"),
        ("f2", "AppDomain-com.kakao.talk", "Documents/KakaoTalk.sqlite"),
        ("f3", "AppDomain-ph.telegra.Telegraph", "Documents/x.db"),
        ("f4", "HomeDomain", "Library/SMS/sms.db"),
    ]
    apps = summarize_apps(rows)
    by_label = {a["label"]: a for a in apps}
    assert by_label["WhatsApp"]["readable"] is True
    assert by_label["KakaoTalk"]["readable"] is False
    assert "앱 자체 암호화" in by_label["KakaoTalk"]["note"]
    assert by_label["Telegram"]["readable"] is False
    assert "HomeDomain" not in by_label
