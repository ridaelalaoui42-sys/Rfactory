# Rfactory AI Asset Library — Original Images + Explicit Fallback

## Goals

Rfactory must use an **actual source image** of a complete animal, figure or object,
rather than old machine-drawn placeholder shapes or unrelated patches of an AI
collage. Every puzzle fragment and destination is extracted from the **same
canonical artwork**. Image model failures are visible and never quietly reported
as successful Gemini generations.

This feature ships on the Rfactory 3.0 PR #2 development branch.

## Asset pack v1 (provided to operator separately)

The downloadable pack created on 2026-10-24 contains:

- One separately generated, **1024×1536 RGBA snow leopard** (OpenAI image
  generation; alpha transparency, no Gemini call).
- Two **HD snow leopard fallback derivatives**: mirrored and warm color grade;
  explicitly labeled as derivatives of the same original, **not** two
  independently generated snow leopards.
- 48 separate **low-resolution reference-only** crops from generated category
  catalog visuals: animals, characters, fantasy, nature/backgrounds.
- Three moodboard catalogs, a visual contact sheet and an SHA-256 manifest.

All source-image records retain the actual original dimensions. Never describe
the small catalog thumbnails as HD originals or silently upscale them into
production. Reference-only cells cannot be approved or used for final videos.

The binary art ZIP is delivered as a conversation download; it is **not embedded
in Git history**. The application can import it from the browser or Android
client with an authenticated ZIP upload, or through a local Python script.

## Install into the library

### Web interface

1. Run the Rfactory backend, open \`/studio\` and connect with the API token.
2. Find **Original artwork library**.
3. Select the supplied Rfactory asset ZIP and click **Install artwork pack**.
4. Filter by category and HD quality. Small reference thumbnails are labeled.
5. Review the full-resolution subject and click **Approve HD asset**.
6. Build a Gemini storyboard (text-only Gemini free access may be available).
7. Confirm artwork rights and stage the selected artwork for video production.
8. Perform the final image approval, then render. No automatic Facebook posting.

### Local command

\`\`\`bash
python -m scripts.import_asset_pack ~/Downloads/Rfactory_Asset_Library_v1.zip
\`\`\`

The importer validates ZIP entry paths, media sizes, SHA-256 checksums,
original-size declarations and image codecs. All imported images remain
unapproved. Previews remain reference-only.

## Generate many new HD original subjects from Gemini

The generator contains original premium-illustration prompts for snow leopard,
red panda, octopus, seahorse, mechanical dragon, astronaut, robot, vehicles,
fantasy subjects and other animals.

\`\`\`bash
# NO provider calls, token usage or billing:
python -m scripts.generate_art_library --dry-run --category animals --count 6

# Only when the image-generation model is accessible on a paid project:
RFACTORY_AI_ENABLED=true GEMINI_API_KEY='set-locally' \
  python -m scripts.generate_art_library --execute \
    --allow-paid-image-api --category animals --count 3 \
    --model gemini-3.1-flash-lite-image
\`\`\`

Use the key only as a server-side environment variable; **never commit,
paste into client JavaScript, expose in mobile apps or print it in logs**.
Generated images enter the same reviewed library with \`provenance=gemini_generated\`
only if the provider returns actual decodable image bytes.

Google's current public Gemini pricing documentation lists API image-generation
models as unavailable on the free tier. A free Gemini text/TTS account therefore
does not guarantee access to Nano Banana image generation:
https://ai.google.dev/gemini-api/docs/pricing

No external generation is mocked as a real provider success.

## Backend APIs

All protected by the existing Rfactory API bearer middleware:

| Method | Endpoint | Function |
|---|---|---|
| GET | \`/api/v1/library/capabilities\` | Library constraints and fallback mode |
| GET | \`/api/v1/library/assets?category=animals\` | Artwork listing & quality badges |
| GET | \`/api/v1/library/assets/{id}\` | Source provenance and QA metadata |
| GET | \`/api/v1/library/media/{id}\` | Authenticated PNG streaming |
| POST | \`/api/v1/library/assets/import\` | Import one user-owned original PNG/JPEG/WebP |
| POST | \`/api/v1/library/import-pack\` | Import signed-by-hash asset manifest ZIP |
| POST | \`/api/v1/library/assets/{id}/approve\` | Operator quality approval |
| POST | \`/api/v1/library/select\` | Deterministic, opt-in HD fallback selection |
| POST | \`/api/v1/library/assets/{id}/stage\` | Stage into Studio; second approval before render |

**Fallback selection example**:

\`\`\`json
{"category":"animals","subject":"snow leopard","allow_fallback":true,"seed":2026}
\`\`\`

If no primary is available and the operator explicitly requests fallback, the
result includes:

\`\`\`json
{
  "selected_as_fallback":true,
  "generation_attempted":false,
  "selection_note":"EXPLICIT FALLBACK: previously generated/curated artwork was reused. No current Gemini image generation occurred."
}
\`\`\`

If no approved HD option exists, the service fails explicitly; it does not
return a cartoon shape or claim that a low-res reference became production art.

## Quality gate

- Preserve original media hash and actual dimensions.
- Original and current shortest dimension must be at least 768 px for a
  production candidate. Higher source sizes are recommended.
- Model-agnostic alpha/segmentation, composition and subject legibility
  remain separately reviewable; passing the resolution gate alone is **not**
  final publishing approval.
- Two reviews: library asset approval, then Studio puzzle-source approval.
- Puzzle QA must validate every exact-fit frame from the canonical source.
- Source provenance must distinguish \`openai_generated\`, \`gemini_generated\`,
  \`openai_generated_derivative\`, \`user_uploaded\` and \`reference_only\`.

## Incomplete or out of scope

- Curated full-resolution animals beyond the snow leopard are not included in
  the first offline pack; reference thumbnails are not adequate for social
  video production. Use paid provider image generation or import licensed HD art.
- No live Gemini image call was executed here.
- The library selector does not silently recover from a failed Gemini request.
  A user must explicitly choose a previously approved fallback.
- Multi-tenant OAuth, cloud object storage, image search/embeddings and mobile
  publishing will require further development.
