# Rfactory Release Import Report

The verified release archive was imported without executing code. No changes were made to `main`.

- Archive: [Apf.zip](https://github.com/ridaelalaoui42-sys/Rfactory/releases/download/Repo/Apf.zip)
- Verified digest: `c025e8c27904ed0205085377022339d5d9915ee08752a148745c116b9850b940`
- Imported: **223** source/static files (29,979,873 bytes)
- Skipped: **4** files
- Generated: 2026-10-23 21:00 UTC

## Files deliberately excluded

| Archive-relative path | Reason |
|---|---|
| `storage/factory.db` | generated/runtime/credential material |
| `storage/exports/sch_47847b7939_lizard/manifest.json` | generated/runtime/credential material |
| `storage/exports/sch_47847b7939_lizard/caption.txt` | generated/runtime/credential material |
| `storage/exports/sch_47847b7939_lizard/cover_1080x1920.png` | generated/runtime/credential material |

## Next steps

Review imported code for correctness, secret management, injection risks and publication safeguards.
Run tests in an isolated CI job with dependency pinning before considering deployment.
The original ZIP remains available in Releases for recovery; no original release files were deleted.
