# ios-backup-vault

Local-only tool to **image (back up) an iPhone** as an encrypted full backup and
**browse it in your browser** — messages, photos/videos, contacts, calls,
WhatsApp, ChatGPT history, Apple Notes — with selective **export** and a
**backup manager** dashboard.

Everything runs on your own machine. Decrypted data never leaves localhost, and
the backup passphrase is only held in memory (entered via `getpass`, never
stored or logged).

> ⚠️ **Privacy**: an iPhone backup contains highly sensitive data. Keep the
> backup folder and your passphrase safe. This tool is for backing up and
> viewing **your own** device.

---

## Features

- **Imaging** — encrypted full backup via `idevicebackup2`, with a pre-flight
  size/space/connection check and minimal device impact.
- **Viewer** (local web UI) — messages (with contact-name mapping), photos &
  videos, contacts, call history, WhatsApp, ChatGPT local cache, Apple Notes.
- **Export** — select conversations / individual messages / rows / media and
  export to **JSON / HTML / CSV / TXT**; media originals bundled into a **zip**
  with original timestamps preserved.
- **Manager** — register backups (including ones **not** created by this tool —
  just point it at any backup folder) and see device info, imaging time, size,
  and encryption status **without** the passphrase. PII (serial/IMEI/phone) is
  masked by default.

---

## Requirements

- **macOS or Linux** (Windows untested).
- **Python ≥ 3.11**
- **libimobiledevice** command-line tools on your `PATH`
  (`idevice_id`, `idevicepair`, `ideviceinfo`, `idevicebackup2`):
  - macOS: `brew install libimobiledevice`
  - Debian/Ubuntu: `sudo apt install libimobiledevice-utils`

---

## Install

```bash
git clone https://github.com/seonbright01/ios-backup-vault.git
cd ios-backup-vault
python3 -m venv .venv
source .venv/bin/activate
pip install .            # or: pip install -r requirements.txt
```

---

## Usage

The CLI entrypoint is `python -m ios_backup_vault.cli`.

```bash
# 1) Pre-flight: connection, device state, estimated size vs. free space
python -m ios_backup_vault.cli precheck --target /path/to/save

# 2) Image (encrypted full backup) into the chosen save path
python -m ios_backup_vault.cli backup   --target /path/to/save
#    -> creates /path/to/save/<UDID>/

# 3) Browse a backup in the local web viewer (prompts for passphrase)
python -m ios_backup_vault.cli view --backup /path/to/save/<UDID>
#    open http://127.0.0.1:8765

# Manager / metadata (no passphrase needed — public plist metadata only)
python -m ios_backup_vault.cli info --backup /path/to/save/<UDID>
python -m ios_backup_vault.cli add  --path   /path/to/any/backup/<UDID>
python -m ios_backup_vault.cli list
python -m ios_backup_vault.cli manage     # web dashboard of all registered backups
```

Connect the iPhone over USB and tap **Trust** before `precheck`/`backup`. For a
complete restorable image (Health, Keychain, app data), enable **encrypted
backup** on the device.

The registry lives at `~/.ios_backup_vault/registry.json` (override with the
`IOS_BACKUP_VAULT_HOME` environment variable).

---

## Security notes

- Local-only: the viewer binds to `127.0.0.1`; nothing is uploaded.
- The passphrase is read with `getpass` and kept in memory only.
- Manager/metadata views read **unencrypted** backup plists only and never need
  the passphrase; PII is masked unless explicitly revealed.

## Limitations

- iMessage/SMS, WhatsApp, ChatGPT, Notes parsing depends on app/iOS schema and
  may need tweaks across versions. Apple Notes exports plain text (tables,
  drawings, and attachments are not rendered).
- Encrypted third-party apps (KakaoTalk, Telegram, Signal, LINE, …) cannot be
  decrypted by this tool.

## Development

```bash
pip install pytest
python -m pytest
```

## License

[MIT](./LICENSE)
