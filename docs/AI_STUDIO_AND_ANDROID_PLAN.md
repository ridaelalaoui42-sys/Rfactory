# Rfactory AI Creative Studio — Production architecture & Android path

Updated: 2026-10-23. Applies to the code in this review branch, not to `main`.

## What is actually implemented

**Real Gemini-backed provider interfaces, behind explicit opt-in:**
- **Planning:** Gemini 3.8 Flash (also selectable 3.6 Flash / 3.5 Flash Lite). Pydantic structured storyboards with a hook, title, image brief, motion plan, captions, voiceover script and art direction.
- **Image:** Nano Banana 2.1, Nano Banana 2 Lite, Nano Banana 2, Nano Banana Pro. Calls the real Gemini Interactions image endpoint, verifies returned bytes, prepares an alpha-cutout subject and checks mask quality. **No silent generic-image fallback**.
- **Image editing:** Submit existing AI asset as a Gemini image reference along with instructions; creates a new version with source-asset provenance and requires renewed approval.
- **Audio:** Gemini 3.8 Flash-Lite TTS or Flash TTS with selectable prebuilt voices and style. Verifies a WAV file, previews it, and supports attaching it as actual audio in FFmpeg.
- **Reel rendering:** `services/engine/renderer.py` now accepts approved image assets and an optional TTS WAV. Existing 1080x1920 procedural animation is retained as the motion compositor; visual content no longer needs to use generic preset illustrations.
- **Review:** AI-generated images initially have `AWAITING_APPROVAL`; video generation checks that the image is `APPROVED`. Video outputs are `READY_FOR_REVIEW` and **not published**.
- **Storage/API:** Files, versioned creative briefs, audit records, and budget counters persist under server-side `storage/ai` and `storage/assets/ai` (not Git). All media is behind authenticated `/api/v1/ai/` routes. A paginated Library endpoint supports future mobile navigation.
- **Responsive web UI:** Real creative flow at `/studio`, featuring editable briefs, image prompt refinement, TTS voice selection/preview, artwork approval, and downloadable verified renders. It makes actual backend requests; no fake success toasts.

**Not verified with a live key:** Model authentication, account quotas, Google billing, rate limiting at Google's end, subjective image quality, provider latency, real narration language/accent quality. Automated tests use SDK-compatible fake responses and validate an end-to-end rendered MP4. This is a key distinction from a live integration test.

**Not yet included:** Native Android binary, Lyria music generation, full AI video generation, asynchronous cloud job delivery, operational analytics, Facebook publishing (existing Playwright module remains a non-live simulator and is blocked), user-based OAuth, role permissions, multi-provider billing dashboards.

## Start locally

Requirements: Python 3.11+, FFmpeg, FFprobe.

```bash
pip install -r requirements-ai.txt

# Linux/macOS; do not commit secrets.
export RFACTORY_AI_ENABLED=true
export GEMINI_API_KEY='YOUR_SECRET_GEMINI_API_KEY'
export RFACTORY_API_TOKEN='SET_A_LONG_RANDOM_SERVER_TOKEN'
export RFACTORY_AI_DAILY_CALL_LIMIT=20

python -m scripts.bootstrap_factory
uvicorn services.api.server:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/studio** and enter the backend bearer token **not your Gemini key**. The Gemini key must remain in server environment variables.

On Windows PowerShell, use `$env:NAME='value'` instead of `export`. The app can also be built as the API-only Docker Compose target by explicitly passing `RFACTORY_AI_ENABLED=true`, `GEMINI_API_KEY`, and `RFACTORY_API_TOKEN` in the deployment environment. Never build them into images.

**Note:** The browser UI and backend must share an origin under this dev setup. For Vercel hosting later, proxy authenticated API requests to a persistent VM; do not store keys or run FFmpeg/Playwright in short-lived serverless functions.

## HTTP API version 1

All `/api/v1/ai` routes use the same bearer token as the management API. The one token is acceptable for local prototype work, **not** public multi-user Android distribution.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/ai/capabilities` | GET | Models, voices, availability, explicit disable status |
| `/api/v1/ai/plans` | POST | Validated Gemini storyboard from `CreativeBrief` |
| `/api/v1/ai/images` | POST | New AI PNG or `source_image_id` image-edit revision |
| `/api/v1/ai/images/{id}/approve` | POST | Operator approval gate |
| `/api/v1/ai/voices` | POST | Gemini WAV narration from text/style/voice |
| `/api/v1/ai/renders` | POST | Produce QA-checked MP4 from plan + approved image + optional WAV |
| `/api/v1/ai/records/{kind}/{id}` | GET | Resume stored projects/assets by stable ID |
| `/api/v1/ai/library?kind=plan&limit=20&offset=0` | GET | Paginated persistent creative-library inventory |
| `/api/v1/ai/media/{kind}/{id}` | GET | Protected PNG/WAV/MP4 delivery |

`GET /openapi.json` returns the machine-readable API schema for future Kotlin/TypeScript clients.

**Controls:** AI calls are explicitly disabled by default, use a hard daily request-count ceiling (`RFACTORY_AI_DAILY_CALL_LIMIT`), size/input bounds, reviewed model allowlists, server-only credentials, and direct error reporting. A request-count ceiling **is not a dollar spend limit**—image/TTS and planning calls cost different amounts. Add per-model pricing, quota and actual billing reconciliation before large-scale automatic campaigns.

## Creative production rules

1. Ask Gemini to produce a differentiated art direction and a *specific* subject, not a generic animal list.
2. For image slicing, produce an original complete isolated illustration with margins and no typography/watermark.
3. Use Gemini image editing and human review to adjust style/lighting/masks. Reject failed QA rather than silently swapping to bundled assets.
4. Use short narration tailored to the puzzle. Choose a language and human-approved voice/persona. Add cinematic cues sparingly.
5. Keep deterministic frame animation for predictable alignment, but use the unique AI subject as the main visual. The current four templates are a foundation; interactive variations and additional motion techniques are a future creative task.
6. Save source prompt/model/variant, approval timestamp, source media lineage, final video, and actual QA outcome. Never fake likes, views or successful publishing.

## Android deployment architecture

### Recommended path: shared web UI → Capacitor for Android

The `apps/studio` UI uses only normal web APIs and a versioned backend contract. It can be rebuilt as a React/TypeScript or other frontend application and packaged using **Capacitor**. Android app UI only handles briefs, previews, artwork approvals, render status, and download/share; processing remains on server.

Alternative: native **Kotlin + Jetpack Compose**, using `/openapi.json` as an API contract. This is best if offline editing, device integrations and Play Store polish become priorities.

### Required before an Android release

- **Authentication:** exchange prototype shared bearer token for real per-user OAuth/OIDC sessions, PKCE and secure token storage. Do not embed Gemini or administrator keys in APK.
- **Background execution:** change synchronous `POST /renders` into an asynchronous persisted job: return `202 + job_id`; poll `GET /jobs/{id}` or use secure WebSocket/push. Use Android WorkManager for intermittent connectivity.
- **Media delivery:** short-lived signed URLs / authenticated range streaming, storage quotas, expiration, proper seekable videos, cleanup, and CDN caching.
- **Mobile design:** offline drafts, device upload and simple editing, battery/network mindful previews, accessibility, landscape/tablet adaptation, error retry, and notifications.
- **Security & ops:** tenant isolation, device/session revocation, usage metering, provider cost tracking, crash analytics, privacy policy, user consent for real-person/voice material, and store compliance.
- **Publishing:** keep browser-based Facebook automation on a managed desktop/VM worker only; do not run it inside the Android app. Do not bypass Meta login challenges or claim posts succeeded without observable confirmation.

### Delivery milestones

1. **MVP (this PR):** Gemini storyboard + premium image/edit + TTS + approved puzzle render + mobile-friendly studio and stable API. Verified with fake SDK and real FFmpeg output.
2. **Production-grade cloud:** persistent AI jobs, image/reference asset library, better visual QA + variety guardrails, more motion templates, role auth, cost ledger, media storage, feedback/analytics and a real authenticated web dashboard.
3. **Android release:** shared client UI wrapped by Capacitor (or Compose), real user accounts, review queue, push notifications, deep links and optimized previews. Submit to Play Store only after live end-to-end tests.

## Official Google API references

- Image creation/editing: https://ai.google.dev/gemini-api/docs/image-generation
- Gemini speech/TTS: https://ai.google.dev/gemini-api/docs/speech-generation
- Schema-controlled planning: https://ai.google.dev/gemini-api/docs/structured-output
- Model catalog: https://ai.google.dev/gemini-api/docs/models

## Gemini Free Tier: what actually works without billing

As of October 23, 2026, Google's public pricing documentation lists free quota access for **Gemini 3.5 Flash-Lite planning** and **Gemini 3.8 Flash / Flash-Lite TTS**, subject to project rate limits. **Nano Banana / Gemini image-generation API requests have no free tier**; selecting an image model does not bypass the billing requirement.

Consequently Rfactory now has a no-paid-image route:
1. Use your Gemini free-tier key for storyboard planning and TTS.
2. Import an original/licensed PNG/JPEG/WebP through the Studio (or `POST /api/v1/ai/images/import`) instead of calling Nano Banana.
3. The imported asset is alpha-segmented, validated and marked `AWAITING_APPROVAL`.
4. Approve the asset, then render locally using the configured puzzle animation and narration.
5. Keep control of ownership/provenance and never auto-post.

To check your key **without embedding it in code, a public repo, or CI logs**:

```bash
python -m scripts.check_gemini_key
```

The script reads the key from `GEMINI_API_KEY` or a hidden terminal prompt, makes a single `models.list` request to Google's official Gemini endpoint, then prints only status and listed model names. It does not generate billable media. A successful listing is *not* proof an account has paid image generation enabled. Do not paste keys in the browser or commit them.

Official pricing: https://ai.google.dev/gemini-api/docs/pricing

