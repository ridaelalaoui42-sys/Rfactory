/* Mobile-first Rfactory Studio, calling REAL versioned API routes.
   No provider/API keys are embedded. The bearer token stays in memory only. */
(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const state = { token: "", plan: null, image: null, voice: null, render: null,
    selectedLibrary: null, libraryItems: [], urls: [] };
  const apiBase = "/api/v1/ai";

  function message(text, category = "") {
    const node = byId("notice");
    node.className = "notice " + category;
    node.textContent = text;
  }
  function output(text) {
    byId("output-status").textContent = text;
  }
  function setBusy(button, on, label) {
    button.disabled = on;
    if (on) {
      button.dataset.previousLabel = button.textContent;
      button.textContent = label || "Working...";
    } else {
      button.textContent = button.dataset.previousLabel || button.textContent;
    }
  }
  async function request(method, path, payload) {
    if (!state.token) throw Error("Connect using your private backend access token first.");
    const headers = { Authorization: "Bearer " + state.token };
    if (payload !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(apiBase + path, {
      method,
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(body.detail || "Request failed (HTTP " + response.status + ")");
    return body;
  }
  async function uploadArtwork(file, planId) {
    if (!state.token) throw Error("Connect your backend first.");
    const form = new FormData();
    form.append("file", file, file.name);
    if (planId) form.append("plan_id", planId);
    const response = await fetch(apiBase + "/images/import", {
      method: "POST",
      headers: {Authorization: "Bearer " + state.token},
      body: form,
      cache: "no-store"
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(body.detail || "Artwork import failed");
    return body;
  }
  async function libraryRequest(method, path, payload) {
    if (!state.token) throw Error("Connect your Rfactory backend first.");
    const headers = {Authorization: "Bearer " + state.token};
    if (payload !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch("/api/v1/library" + path, {
      method, headers, cache:"no-store",
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(result.detail || "Asset library request failed");
    return result;
  }
  function refreshLibraryControls() {
    const asset = state.selectedLibrary;
    byId("library-approve-btn").disabled =
      !asset || !asset.production_eligible || asset.approved;
    byId("library-stage-btn").disabled =
      !asset || !asset.production_eligible || !asset.approved ||
      !state.plan || !byId("library-rights").checked;
    byId("library-render-btn").disabled =
      !asset || !asset.production_eligible || !asset.approved ||
      !byId("library-rights").checked;
  }
  async function loadArtworkLibrary() {
    const category = byId("library-category").value;
    const productionOnly = byId("library-quality").value === "production";
    const result = await libraryRequest("GET",
      "/assets?category=" + encodeURIComponent(category) +
      "&production_only=" + (productionOnly ? "true" : "false") + "&limit=100");
    state.libraryItems = result.items;
    const grid = byId("library-grid");
    grid.replaceChildren();
    state.selectedLibrary = null;
    byId("library-selection").textContent = "Choose an image to inspect source and quality.";
    const records = result.items.slice(0, 24);
    byId("library-status").textContent =
      result.items.length + " matching images · " +
      result.items.filter(item => item.production_eligible).length +
      " HD candidates · " + records.length + " previews displayed";
    for (const item of records) {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "library-tile";
      card.setAttribute("aria-label", "Select " + item.subject);
      const image = document.createElement("img");
      image.alt = item.subject;
      image.loading = "lazy";
      const title = document.createElement("strong");
      title.textContent = item.subject;
      const badge = document.createElement("small");
      badge.textContent = item.production_eligible
        ? (item.is_fallback ? "FALLBACK · HD" : "HD · " + item.tier)
        : "REFERENCE ONLY";
      card.append(image, title, badge);
      card.addEventListener("click", () => {
        state.selectedLibrary = item;
        grid.querySelectorAll(".library-tile").forEach(el => el.classList.remove("selected"));
        card.classList.add("selected");
        byId("library-selection").textContent =
          item.subject + " · " + item.width + "×" + item.height +
          " · " + item.provenance + " · " + item.review_status +
          (item.is_fallback ? " · explicit fallback artwork" : "") +
          (item.production_eligible ? "" : " · not usable in a final Reel");
        refreshLibraryControls();
      });
      grid.append(card);
      // Protected blob URLs: never expose an administrator bearer token in src.
      protectedMedia(item.media_url).then(url => {
        if (card.isConnected) image.src = url;
      }).catch(() => { badge.textContent += " · preview unavailable"; });
    }
    refreshLibraryControls();
  }
  async function importArtworkPack(file) {
    if (!state.token) throw Error("Connect first.");
    if (!file || file.size > 60 * 1024 * 1024) {
      throw Error("Select a valid Rfactory ZIP under 60 MB.");
    }
    const data = new FormData();
    data.append("file", file, file.name);
    const response = await fetch("/api/v1/library/import-pack", {
      method:"POST", headers:{Authorization:"Bearer " + state.token},
      body:data, cache:"no-store",
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(body.detail || "Artwork-pack import failed");
    return body;
  }
  async function protectedMedia(relativeUrl) {
    const response = await fetch(relativeUrl, {
      headers: { Authorization: "Bearer " + state.token }, cache: "no-store",
    });
    if (!response.ok) throw Error("Could not read generated media (HTTP " + response.status + ")");
    const objectUrl = URL.createObjectURL(await response.blob());
    state.urls.push(objectUrl);
    return objectUrl;
  }
  function activatePreview(elementName, url) {
    byId("placeholder").hidden = true;
    byId("video-preview").hidden = elementName !== "video";
    byId("image-preview").hidden = elementName !== "image";
    const target = byId(elementName === "video" ? "video-preview" : "image-preview");
    target.src = url;
  }
  function handle(button, messageText, callback) {
    button.addEventListener("click", async () => {
      setBusy(button, true, messageText);
      try {
        await callback();
      } catch (error) {
        message(error.message || "Unexpected error", "error");
        output("Action failed. No fabricated fallback was used.");
      } finally {
        setBusy(button, false);
        updateButtons();
      }
    });
  }
  function updateButtons() {
    byId("image-btn").disabled = !state.plan;
    byId("voice-btn").disabled = !state.plan;
    byId("refine-btn").disabled = !state.image;
    byId("approve-btn").disabled = !state.image || state.image.status === "APPROVED";
    byId("render-btn").disabled = !state.plan || !state.image || state.image.status !== "APPROVED";
    refreshLibraryControls();
  }
  function resetFromPlan() {
    state.image = null;
    state.voice = null;
    state.render = null;
    byId("image-preview").hidden = true;
    byId("video-preview").hidden = true;
    byId("voice-preview").hidden = true;
    byId("download").hidden = true;
    byId("placeholder").hidden = false;
    byId("art-status").textContent = "Generate unique AI artwork using the director's prompt.";
    updateButtons();
  }
  handle(byId("library-import-btn"), "Importing artwork ZIP...", async () => {
    const file = byId("library-pack-file").files[0];
    const result = await importArtworkPack(file);
    message("Installed " + result.imported + " assets: " +
      result.production_candidates + " HD candidates, " +
      result.reference_only + " preview-only references. Review before use.", "ok");
    await loadArtworkLibrary();
  });
  handle(byId("library-refresh-btn"), "Refreshing...", async () => {
    await loadArtworkLibrary();
  });
  byId("library-category").addEventListener("change", () => {
    loadArtworkLibrary().catch(error => message(error.message, "error"));
  });
  byId("library-quality").addEventListener("change", () => {
    loadArtworkLibrary().catch(error => message(error.message, "error"));
  });
  byId("library-rights").addEventListener("change", refreshLibraryControls);
  handle(byId("library-approve-btn"), "Reviewing HD asset...", async () => {
    if (!state.selectedLibrary) throw Error("Select a production-quality asset.");
    const record = await libraryRequest("POST",
      "/assets/" + state.selectedLibrary.id + "/approve");
    state.selectedLibrary = record;
    message("Approved " + record.subject + " as a vetted original artwork source.", "ok");
    await loadArtworkLibrary();
  });
  handle(byId("library-render-btn"), "Rendering real-image MP4...", async () => {
    const art = state.selectedLibrary;
    if (!art || !art.approved || !art.production_eligible ||
        !byId("library-rights").checked) {
      throw Error("Approve real HD artwork and confirm your rights before rendering.");
    }
    const result = await libraryRequest("POST", "/renders", {
      asset_id: art.id,
      allow_fallback: Boolean(art.is_fallback),
      geometry: byId("library-cutout").value,
      motion_profile: byId("library-motion").value,
      duration_sec: Number(byId("library-duration").value),
      exact_fit_count: Number(byId("library-fits").value),
      enable_sfx: byId("library-sfx").checked,
      seed: (Date.now() >>> 0) % 2147483647
    });
    const url = await protectedMedia(result.video_url);
    byId("library-video-player").src = url;
    byId("library-video-download").href = url;
    byId("library-video-result").hidden = false;
    byId("library-video-qa").textContent =
      "Verified " + result.decoded_frames_checked + " frames · raw alignment MAD " +
      result.raw_alignment_mad + " · exact fits: " +
      result.exact_fit_times_sec.map(t => Number(t).toFixed(2) + "s").join(", ") +
      " · " + (result.fallback_used ? "explicit fallback source" : "original approved source") +
      " · NOT PUBLISHED";
    message("Finished MP4 ready: " + result.id + ". Video passed alignment and frame QA.", "ok");
  });
  handle(byId("library-stage-btn"), "Preparing artwork for Reel...", async () => {
    if (!state.selectedLibrary || !state.plan || !byId("library-rights").checked) {
      throw Error("Select an approved HD image, create a storyboard and confirm artwork rights.");
    }
    const result = await libraryRequest("POST",
      "/assets/" + state.selectedLibrary.id + "/stage", {
        plan_id: state.plan.id, acknowledge_source_license: true
      });
    state.image = result;
    activatePreview("image", await protectedMedia(state.image.media_url));
    byId("production-panel").hidden = false;
    byId("art-status").textContent =
      "Library asset staged: " + (result.fallback_used ? "EXPLICIT FALLBACK" : "approved original") +
      " · image approval required before rendering.";
    message("Artwork staged from the library; no Gemini image generation was claimed.", "ok");
    output("Review the art and approve the staged image to render this puzzle.");
    updateButtons();
  });
  handle(byId("connect"), "Connecting...", async () => {
    const token = byId("api-token").value.trim();
    if (!token) throw Error("Enter your backend access token.");
    state.token = token;
    const caps = await request("GET", "/capabilities");
    if (!caps.ai_enabled || !caps.configured) {
      message("Connected to Rfactory asset library. Gemini is unavailable; browsing, uploading and reviewing artwork remain accessible.", "ok");
      output("To generate a storyboard, enable Gemini on the backend. Asset importing does not need image-generation credits.");
      await loadArtworkLibrary();
      return;
    }
    byId("connection-state").textContent = "Connected to Gemini-ready backend";
    document.querySelector(".led").classList.add("on");
    message("Studio connected. Gemini image, storyboard and TTS capabilities are available.", "ok");
    byId("api-token").value = "";
    byId("api-token").placeholder = "Token loaded for this session";
    await loadArtworkLibrary();
  });
  handle(byId("plan-btn"), "Directing with Gemini...", async () => {
    const brief = {
      topic: byId("topic").value,
      audience: "Creative visual puzzle Reel viewers",
      language: byId("language").value,
      style: byId("style").value,
      template: byId("template").value,
      brand: "Rfactory Originals",
      twist: byId("twist").value,
      duration_sec: Number(byId("duration").value),
    };
    state.plan = await request("POST", "/plans", { brief });
    resetFromPlan();
    const creative = state.plan.plan;
    byId("plan-title").textContent = creative.title;
    byId("plan-hook").textContent = creative.hook;
    byId("motion-direction").textContent =
      "Gemini-chosen movement: " + (creative.motion_profile || "orbit_lock") +
      " · " + (creative.motion_note || "Puzzle motion") +
      " · " + (creative.cycles || 5) + " cycles";
    byId("image-prompt").value = creative.image_prompt;
    byId("voice-script").value = creative.narration;
    byId("storyboard-panel").hidden = false;
    byId("production-panel").hidden = false;
    message("Original Gemini storyboard created. Review and edit the art/voice prompts.", "ok");
    output("Storyboard ready: " + creative.title + ". No image or voice credits have been used yet.");
    updateButtons();
  });
  handle(byId("upload-btn"), "Validating your artwork...", async () => {
    if (!state.plan) throw Error("Create a storyboard before importing artwork.");
    const file = byId("artwork-file").files[0];
    if (!file) throw Error("Select an original PNG, JPEG or WebP image first.");
    if (file.size > 10 * 1024 * 1024) throw Error("Please choose an image under 10 MB.");
    state.image = await uploadArtwork(file, state.plan.id);
    activatePreview("image", await protectedMedia(state.image.media_url));
    byId("download").hidden = true;
    byId("art-status").textContent =
       "Artwork imported and mask QA passed. Verify you own the rights, then approve it.";
    message("Artwork imported locally without paid image generation.", "ok");
    output("Imported image ready for approval. Gemini image credits were not used.");
    updateButtons();
    refreshLibraryControls();
  });
  handle(byId("image-btn"), "Generating Nano Banana artwork...", async () => {
    if (!state.plan) throw Error("Create a storyboard first.");
    state.image = await request("POST", "/images", {
      plan_id: state.plan.id,
      prompt: byId("image-prompt").value,
      style: byId("style").value,
      model: byId("image-model").value,
      transparent_subject: true,
    });
    activatePreview("image", await protectedMedia(state.image.media_url));
    byId("download").hidden = true;
    byId("art-status").textContent = "Unique artwork produced by " + state.image.model +
      ". Segmentation QA: passed. Please inspect details and approve.";
    message("AI artwork generated successfully. Review it before rendering.", "ok");
    output("Artwork is awaiting manual approval. Provider: " + state.image.provider);
    updateButtons();
  });
  handle(byId("refine-btn"), "Refining artwork...", async () => {
    if (!state.image || !state.plan) throw Error("Generate original artwork first.");
    const sourceId = state.image.id;
    state.image = await request("POST", "/images", {
      plan_id: state.plan.id,
      source_image_id: sourceId,
      prompt: byId("edit-prompt").value,
      style: byId("style").value,
      model: byId("image-model").value,
      transparent_subject: true,
    });
    activatePreview("image", await protectedMedia(state.image.media_url));
    byId("download").hidden = true;
    byId("art-status").textContent = "New Gemini image revision is ready for visual inspection. Approval reset.";
    message("Artwork revised. Review and approve this new version before rendering.", "ok");
    output("Revision generated from artwork " + sourceId.slice(0, 8) + ". Previous version remains saved.");
  });
  handle(byId("voice-btn"), "Generating Gemini narration...", async () => {
    if (!state.plan) throw Error("Create a storyboard first.");
    state.voice = await request("POST", "/voices", {
      plan_id: state.plan.id,
      text: byId("voice-script").value,
      style: byId("voice-style").value || state.plan.plan.audio_style,
      language: byId("language").value,
      voice: byId("tts-voice").value,
      model: byId("tts-model").value,
    });
    byId("voice-preview").src = await protectedMedia(state.voice.media_url);
    byId("voice-preview").hidden = false;
    message("AI narration is ready. Listen to the generated voice before rendering.", "ok");
    output("Narration generated via " + state.voice.model + ". You can render with this voice.");
  });
  handle(byId("approve-btn"), "Approving...", async () => {
    if (!state.image) throw Error("Generate artwork before approving.");
    state.image = await request("POST", "/images/" + state.image.id + "/approve");
    byId("art-status").textContent = "✓ Artwork approved for this Reel.";
    message("Artwork approved. The renderer can now use this exact generated subject.", "ok");
  });
  handle(byId("motion-preview-btn"), "Checking motion...", async () => {
    if (!state.token) throw Error("Enter your backend access token before previewing.");
    const params = {
      profile: byId("motion-profile").value || state.plan?.plan?.motion_profile || "orbit_lock",
      fps: 30,
      duration_sec: Number(byId("duration").value),
      crossing_count: Number(byId("snap-count").value) || 5,
      seed: 42041,
      travel_px: 210,
      intensity: Number(byId("motion-intensity").value),
      samples: 320,
    };
    const result = await fetch("/api/v1/creative/motion/preview", {
      method: "POST",
      headers: {"Content-Type":"application/json",Authorization:"Bearer "+state.token},
      body: JSON.stringify(params),
      cache: "no-store"
    });
    const reply = await result.json();
    if (!result.ok) throw Error(reply.detail || "Motion preview failed");
    const maxDist = Math.max(1, ...reply.samples.map(p => Math.max(Math.abs(p.x),Math.abs(p.y))));
    const factor = Math.min(0.78,110 / maxDist);
    const points = reply.samples.map(p => [
      +(180+p.x*factor).toFixed(2),
      +(120+p.y*factor).toFixed(2)
    ]);
    byId("motion-svg-path").setAttribute("d", points.map((xy,i) =>
      (i ? "L" : "M") + xy[0]+" "+xy[1]).join(" "));
    byId("motion-inspector").hidden = false;
    byId("motion-inspector-count").textContent = reply.crossing_count + " crossings";
    byId("motion-preview-times").textContent =
      "Exact-fit frames: " + reply.crossing_frames.join(", ") +
      " · at " + reply.crossing_times_sec.map(t => t.toFixed(2)+"s").join(" · ") +
      " · no pause or exported visual hints.";
    message("Real deterministic motion path loaded; crossing markers are preview-only.", "ok");
  });
  handle(byId("render-btn"), "Rendering Reel on server...", async () => {
    if (!state.plan || !state.image || state.image.status !== "APPROVED") {
      throw Error("Approve AI artwork before rendering.");
    }
    state.render = await request("POST", "/renders", {
      plan_id: state.plan.id,
      image_id: state.image.id,
      voice_id: state.voice ? state.voice.id : null,
      duration_sec: Number(byId("duration").value),
      sfx_enabled: byId("sfx-enabled").checked,
      motion_profile: byId("motion-profile").value || null,
      puzzle_geometry: byId("puzzle-geometry").value,
      motion_intensity: Number(byId("motion-intensity").value),
      snap_count: Number(byId("snap-count").value),
    });
    const url = await protectedMedia(state.render.media_url);
    activatePreview("video", url);
    const link = byId("download");
    link.href = url;
    link.hidden = false;
    output("Video QA passed · " + state.render.qa.duration_sec + "s · " +
      state.render.qa.codec.toUpperCase() + " · " +
      (state.render.snap_count || "several") +
      " irregular exact-fit moments. Ready for review. NOT PUBLISHED.");
    message("Your AI-powered puzzle Reel has rendered successfully!", "ok");
  });
  byId("motion-intensity").addEventListener("input", () => {
    byId("motion-value").textContent = Number(byId("motion-intensity").value).toFixed(1) + "×";
  });
  updateButtons();
  window.addEventListener("pagehide", () => {
    state.urls.forEach((url) => URL.revokeObjectURL(url));
    state.token = "";
  });
})();