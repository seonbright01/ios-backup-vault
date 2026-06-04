# ios-backup-vault

Local-only tool to **image (back up) an iPhone** as an encrypted full backup and
**browse it in your browser** — messages, photos/videos, contacts, calls,
WhatsApp, ChatGPT history, Apple Notes — with selective **export**, a
**backup manager** dashboard, and an optional **cloud archive (GCS)** that keeps
only ciphertext in the cloud while decryption stays on your Mac.

Everything that touches your data runs on your own machine. Decrypted data never
leaves localhost, and the backup passphrase is only held in memory (entered via
`getpass`, never stored or logged).

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
- **Cloud archive (GCS)** — mirror an encrypted backup to a Google Cloud Storage
  bucket as **ciphertext only**, then browse it from the manager dashboard by
  fetching just the files you open, on demand. Decryption and the passphrase
  never leave your Mac.

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

For the cloud archive feature, install the optional `[gcs]` extra (see
[Cloud archive (GCS)](#cloud-archive-gcs) below):

```bash
pip install ios-backup-vault[gcs]
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

## Cloud archive (GCS)

Mirror an **encrypted** backup to a Google Cloud Storage bucket, then open it
from the manager dashboard. Only ciphertext is stored in the cloud; the
passphrase and all decryption stay on your Mac.

### Install

```bash
pip install ios-backup-vault[gcs]      # optional extra: google-cloud-storage
```

### Credentials (Application Default Credentials recommended)

This tool **stores no credentials**. With the recommended `--auth adc` mode it
relies on Google's Application Default Credentials:

```bash
# Option A — interactive login (recommended)
gcloud auth application-default login

# Option B — point at a service-account key file
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

> Optional: if you prefer to keep a service-account key out of the environment,
> `--auth keyring --key-file <path>` stores the key in the OS keyring (requires
> the `keyring` package) and offers to delete the plaintext key file afterward.
> ADC is still the recommended path.

### IAM — least privilege

Grant **only** `roles/storage.objectAdmin` **scoped to the single bucket** used
for the vault. Do **not** add a project-wide binding.

```bash
gsutil iam ch \
  user:you@example.com:roles/storage.objectAdmin \
  gs://<bucket>
```

### Flow

```bash
# 1) Save cloud config (provider gcs, bucket, prefix, auth mode)
python -m ios_backup_vault.cli cloud-config --bucket <bucket> --prefix vault --auth adc

# 2) Upload an encrypted backup as ciphertext (optionally clear the local copy)
python -m ios_backup_vault.cli cloud-upload --backup backups/<UDID> --udid <UDID> [--delete-local]

# 3) List archived devices
python -m ios_backup_vault.cli cloud-list

# 4) Browse from the dashboard: manage -> cloud card [열기] -> enter passphrase
#    -> view / export, fetching only the files you open
python -m ios_backup_vault.cli manage
```

`--delete-local` removes the local backup folder **only after** an integrity
gate confirms every file was uploaded at the correct size; on any mismatch the
local copy is kept.

### How it works

The cloud holds **encrypted backup data (ciphertext) only**. Decryption and the
passphrase happen **on your Mac alone**. When you browse, only the **files you
actually open** are fetched on demand into a size-capped LRU cache (with a
**Clear cache** button in the dashboard); metadata (`Manifest.plist`/
`Manifest.db`) is fetched once so the listing loads immediately.

### Platform & security notes

- Decryption is **local-only** and the viewer binds to `127.0.0.1`; the
  passphrase and decrypted plaintext are **never sent to the cloud**.
- On **macOS**, credentials can come from the system Keychain (or ADC). On
  **Linux/Windows**, **ADC is recommended** because it avoids the macOS
  `security` tooling dependency.
- **FileVault / full-disk encryption is strongly recommended** so that cached
  ciphertext and any temporary decrypted plaintext on disk are protected at
  rest.

### Limitations (cloud)

- **Imaging requires a local USB connection.** Creating a backup cannot be done
  from a serverless cloud — the device must be physically connected to your Mac.
- **GCS egress costs** apply when fetching files for viewing or export.
- **Restore** likewise needs a local download of the backup followed by a USB
  connection to the device.

---

## Security notes

- Local-only: the viewer binds to `127.0.0.1`; nothing is uploaded except, when
  you opt in, the **encrypted** backup to your own GCS bucket.
- The passphrase is read with `getpass` and kept in memory only — never stored,
  logged, or sent to the cloud.
- Manager/metadata views read **unencrypted** backup plists only and never need
  the passphrase; PII is masked unless explicitly revealed.

## Limitations

- iMessage/SMS, WhatsApp, ChatGPT, Notes parsing depends on app/iOS schema and
  may need tweaks across versions. Apple Notes exports plain text (tables,
  drawings, and attachments are not rendered).
- Encrypted third-party apps (KakaoTalk, Telegram, Signal, LINE, …) cannot be
  decrypted by this tool.
- Imaging requires a local USB connection (no serverless/cloud imaging), and the
  cloud archive incurs GCS egress costs when files are fetched. See
  [Cloud archive (GCS)](#cloud-archive-gcs).

## Development

```bash
pip install pytest
python -m pytest
```

## License

[MIT](./LICENSE)
