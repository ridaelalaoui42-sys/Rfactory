# ClipForge next engineering phases

## Implemented
- Metadata-only YouTube Data API search; typed transcript JSON normalization, permanent timestamped search index.
- Source rights labels with evidence and fail-closed unattended render gate.
- Multiple cut ranges, 9:16 + 16:9 + 1:1 visual layouts, FFmpeg rough cuts.
- Original Editor V1 availability probe and JSON editing briefs (original third-party files kept private).
- Local CLI, authenticated admin API, reproducible Docker file and automated tests.

## Still to build
1. Distributed processing: Postgres, Redis, async workers, object storage, retry and job idempotency.
2. Integrated ytb-cli metadata adapter, stored topic feeds, transcript discovery from permitted sources, creator submissions and video segment timecodes.
3. Whisper/Darija/French/English transcriber, speaker tracking, original-language subtitle correction.
4. LLM-powered scoring that selects complete ideas, excludes out-of-context quotes and generates unique scripts.
5. Original Editor V1 execution: use private skill at CLIPFORGE_EDITOR_V1_PATH, audited dependencies and isolated rendering runner. Never copy its upstream assets into the public repository.
6. HyperFrames and GSAP motion graphics, original B-roll, social captions, reframe/face tracking, long-form chapter timeline.
7. Next.js production dashboard for topics, media rights, approval, clips, editing styles and QA.
8. Official YouTube Data API/Meta Graph API OAuth publishing (Playwright only for testing our own UI).
9. Revenue/retention analytics and experimentation loops.
10. Operational hardening: tenant isolation, signed uploads, virus scan, source contracts, secrets vault, rate limits, audit logs and backups.

No footage download circumvention, no automated fair-use approval and no unreviewed reposting.
