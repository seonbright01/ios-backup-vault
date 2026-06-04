import json
from ios_backup_vault import cli


class FakeStore:
    def __init__(self): self.objs = {}
    def put_from_file(self, rel, f): self.objs[rel] = f.read()
    def head(self, rel):
        d = self.objs.get(rel); return {"size": len(d), "generation": 1} if d is not None else None
    def list_udids(self): return sorted({k.split("/")[0] for k in self.objs})


def test_config_adc_then_upload_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("IOS_BACKUP_VAULT_HOME", str(tmp_path))
    rc = cli.main(["cloud-config", "--bucket", "B", "--prefix", "v", "--auth", "adc"])
    assert rc == 0
    cfg = json.load(open(tmp_path / "cloud.json"))
    assert cfg["bucket"] == "B" and cfg["auth"] == "adc" and cfg["provider"] == "gcs"

    bk = tmp_path / "UDID"; bk.mkdir()
    (bk / "Manifest.plist").write_bytes(b"mp"); (bk / "Status.plist").write_bytes(b"sp")
    fake = FakeStore()
    monkeypatch.setattr(cli, "_make_store", lambda: fake)
    assert cli.main(["cloud-upload", "--backup", str(bk), "--udid", "UDID"]) == 0
    assert "UDID/Status.plist" in fake.objs
    assert cli.main(["cloud-list"]) == 0
    assert "UDID" in capsys.readouterr().out
