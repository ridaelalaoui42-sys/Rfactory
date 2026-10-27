# Authorized private/draft publishing

ClipForge can stage completed authorized exports to YouTube as private videos and Facebook as draft Reels. Public publishing, ad eligibility, monetization and external account onboarding are not automatic. An operator must explicitly approve each destination for each completed plan.

## Prerequisites
- The content owner grants the required rights, including music and supplementary assets.
- YouTube: obtain your own OAuth2 refreshable user credentials with youtube.upload scope; mount the authorized_user JSON outside Git and configure CLIPFORGE_YOUTUBE_OAUTH_JSON to point to it. Refresh authorization when required.
- Meta: obtain appropriate Page-level access token and permissions using the official Meta developer workflow. Configure CLIPFORGE_META_PAGE_TOKEN and CLIPFORGE_META_GRAPH_VERSION. These values must be passed to the worker as secrets, not checked into Git.
- Install optional publishing dependencies with pip install -e ".[publish]" or use the Docker image.
- The worker must run to execute queued uploads.

## API sequence (Bearer CLIPFORGE_API_TOKEN required)
1. Create and complete a video render plan using approved source media.
2. POST /v1/plans/{id}/approve-publication with JSON body {"destination":"youtube"} or {"destination":"facebook"}.
3. POST /v1/plans/{id}/queue-publish-draft with {"destination":"youtube","title":"Video title","description":"Original editorial notes"}.
4. Observe GET /v1/jobs/{job_id} until complete or failed.
5. Verify the uploaded video manually in YouTube Studio or Meta Page management.
6. Release the video publicly only after creator/platform and copyright requirements are met.

YouTube output state is always private. Meta Reel state is always DRAFT. Facebook API compatibility is limited to conservatively validated 4–60 second portrait clips until account-specific capabilities have been checked.

## Important safeguards
- This is not a token-provisioning or social account creation tool.
- No Playwright automation of platform login, anti-bot bypass or large-scale duplicate reposting.
- Approval is blocked if the source is unresolved, unlicensed or marked fair_use_review.
- Duplicate uploads of completed jobs are blocked by locally recorded external IDs. If a network call fails mid-upload, reconcile the platform state before attempting to resubmit.
- Credentials and OAuth tokens must remain operator secrets.
