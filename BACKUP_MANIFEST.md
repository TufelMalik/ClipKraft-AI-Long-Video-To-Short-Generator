# Upstream Backup Manifest

This repository preserves an independently hosted snapshot of the OpenShorts source code.

## Verified snapshot

- Original repository: `https://github.com/mutonby/openshorts`
- Upstream commit: `89b4074986c2b5fa8ffcac862116f2d3368d4223`
- Backup tag: `openshorts-upstream-2026-10-13`
- Source archive: `openshorts-main.zip`
- Archive SHA-256: `3FF6E49D6F40155F75774B6538AF59637299B1305B66B0092CCC61C4605661FA`

The downloaded archive and the tagged Git tree contain the same 416 files. Their contents match after normalizing Windows CRLF and Unix LF line endings.

The archive itself is intentionally not committed because it duplicates the Git tree and would make the repository unnecessarily large. The immutable tag preserves the exact source snapshot in GitHub.

## Restore the exact upstream snapshot

```powershell
git clone https://github.com/TufelMalik/OpenShort-Long-Video-To-Short-Generator.git
cd OpenShort-Long-Video-To-Short-Generator
git checkout openshorts-upstream-2026-10-13
```

## Security

Local `.env` files, API-key text files, credentials, private keys, uploaded media, and generated output are excluded from the repository. No local API key is part of this snapshot or manifest.
