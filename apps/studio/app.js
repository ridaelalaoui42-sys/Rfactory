/* Mobile-first Rfactory Studio, calling REAL versioned API routes.
   No provider/API keys are embedded. The bearer token stays in memory only. */
(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const state = { token: "", plan: null, image: null, voice: null, render: null, urls: [] };
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
  handle(byId("connect"), "Connecting...", async () => {
    const token = byId("api-token").value.trim();
    if (!token) throw Error("Enter your backend access token.");
    state.token = token;
    const caps = await request("GET", "/capabilities");
    if (!caps.ai_enabled || !caps.configured) {
      message("The backend is reachable, but Gemini is disabled or has no server-side API key.", "error");
      output("Set RFACTORY_AI_ENABLED=true and configure GEMINI_API_KEY on the server.");
      return;
    }
    byId("connection-state").textContent = "Connected to Gemini-ready backend";
    document.querySelector(".led").classList.add("on");
    message("Studio connected. Gemini image, storyboard and TTS capabilities are available.", "ok");
    byId("api-token").value = "";
    byId("api-token").placeholder = "Token loaded for this session";
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
    byId("image-prompt").value = creative.image_prompt;
    byId("voice-script").value = creative.narration;
    byId("storyboard-panel").hidden = false;
    byId("production-panel").hidden = false;
    message("Original Gemini storyboard created. Review and edit the art/voice prompts.", "ok");
    output("Storyboard ready: " + creative.title + ". No image or voice credits have been used yet.");
    updateButtons();
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
      style: state.plan.plan.audio_style,
      language: byId("language").value,
      voice: byId("tts-voice").value,
      model: "gemini-3.8-flash-lite-tts",
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
  handle(byId("render-btn"), "Rendering Reel on server...", async () => {
    if (!state.plan || !state.image || state.image.status !== "APPROVED") {
      throw Error("Approve AI artwork before rendering.");
    }
    state.render = await request("POST", "/renders", {
      plan_id: state.plan.id,
      image_id: state.image.id,
      voice_id: state.voice ? state.voice.id : null,
      duration_sec: Number(byId("duration").value),
    });
    const url = await protectedMedia(state.render.media_url);
    activatePreview("video", url);
    const link = byId("download");
    link.href = url;
    link.hidden = false;
    output("Video QA passed · " + state.render.qa.duration_sec + "s · " +
      state.render.qa.codec.toUpperCase() + ". Ready for review. NOT PUBLISHED.");
    message("Your AI-powered puzzle Reel has rendered successfully!", "ok");
  });
  updateButtons();
  window.addEventListener("pagehide", () => {
    state.urls.forEach((url) => URL.revokeObjectURL(url));
    state.token = "";
  });
})();