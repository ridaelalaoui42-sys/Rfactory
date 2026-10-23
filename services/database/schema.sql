-- Animal Puzzle Reels Factory — Complete 16-Table Relational Schema
-- Compatible with PostgreSQL 15+ (Supabase) and SQLite 3.35+

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'ADMIN',
    timezone TEXT NOT NULL DEFAULT 'Africa/Casablanca',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    default_language TEXT NOT NULL DEFAULT 'en',
    primary_color_hex TEXT NOT NULL DEFAULT '#183AF5',
    default_bg_hex TEXT NOT NULL DEFAULT '#F2FAFF',
    watermark_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facebook_pages (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    page_name TEXT NOT NULL,
    page_external_id TEXT UNIQUE NOT NULL,
    page_url TEXT NOT NULL,
    session_profile_dir TEXT NOT NULL,
    session_status TEXT NOT NULL DEFAULT 'DISCONNECTED',
    browser_publishing_enabled INTEGER NOT NULL DEFAULT 0,
    daily_post_cap INTEGER NOT NULL DEFAULT 2,
    quiet_hours_start TEXT NOT NULL DEFAULT '23:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '07:00',
    timezone TEXT NOT NULL DEFAULT 'Africa/Casablanca',
    active_lock_job_id TEXT,
    last_heartbeat_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    species TEXT NOT NULL,
    category TEXT NOT NULL,
    template_affinity TEXT NOT NULL,
    png_path TEXT NOT NULL,
    svg_path TEXT,
    outline_png_path TEXT,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    seed INTEGER NOT NULL,
    provenance TEXT NOT NULL,
    license TEXT NOT NULL,
    validation_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_masks (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    mask_type TEXT NOT NULL,
    base_png_path TEXT NOT NULL,
    piece_png_path TEXT,
    slice_bounds_json TEXT NOT NULL,
    alignment_target_xy_json TEXT NOT NULL,
    pixel_match_mad REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    species TEXT NOT NULL,
    template_id TEXT NOT NULL,
    title TEXT NOT NULL,
    hook_question TEXT NOT NULL,
    caption TEXT NOT NULL,
    hashtags TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    seed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS video_projects (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    page_id TEXT REFERENCES facebook_pages(id),
    idea_id TEXT REFERENCES ideas(id),
    title TEXT NOT NULL,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL DEFAULT '1.0.0',
    species TEXT NOT NULL,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    mask_id TEXT REFERENCES asset_masks(id),
    seed INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    caption TEXT NOT NULL,
    engagement_question TEXT NOT NULL,
    hashtags TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    render_status TEXT NOT NULL DEFAULT 'DRAFT',
    publish_status TEXT NOT NULL DEFAULT 'DRAFT',
    content_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    name TEXT NOT NULL,
    requested_count INTEGER NOT NULL,
    completed_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    template_filter TEXT NOT NULL DEFAULT 'BOTH',
    language TEXT NOT NULL DEFAULT 'en',
    target_duration_sec REAL NOT NULL DEFAULT 15.0,
    enable_audio INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS render_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(id),
    batch_id TEXT REFERENCES batches(id),
    status TEXT NOT NULL DEFAULT 'QUEUED',
    progress_pct INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    worker_id TEXT,
    error_log TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS render_outputs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES render_jobs(id),
    project_id TEXT NOT NULL REFERENCES video_projects(id),
    mp4_path TEXT NOT NULL,
    thumbnail_path TEXT NOT NULL,
    alignment_frame_png_path TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    fps REAL NOT NULL,
    duration_sec REAL NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    pixel_match_mad REAL NOT NULL,
    qa_passed INTEGER NOT NULL,
    qa_report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(id),
    page_id TEXT NOT NULL REFERENCES facebook_pages(id),
    scheduled_for_utc TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Africa/Casablanca',
    publisher_mode TEXT NOT NULL DEFAULT 'MANUAL_EXPORT',
    status TEXT NOT NULL DEFAULT 'SCHEDULED',
    idempotency_key TEXT UNIQUE NOT NULL,
    export_bundle_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publish_attempts (
    id TEXT PRIMARY KEY,
    scheduled_post_id TEXT NOT NULL REFERENCES scheduled_posts(id),
    page_id TEXT NOT NULL REFERENCES facebook_pages(id),
    adapter_name TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    failure_taxonomy TEXT,
    trace_log_json TEXT NOT NULL,
    sanitized_screenshot_path TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS published_posts (
    id TEXT PRIMARY KEY,
    scheduled_post_id TEXT UNIQUE NOT NULL REFERENCES scheduled_posts(id),
    page_id TEXT NOT NULL REFERENCES facebook_pages(id),
    project_id TEXT NOT NULL REFERENCES video_projects(id),
    external_permalink TEXT,
    confirmation_method TEXT NOT NULL,
    published_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id TEXT PRIMARY KEY,
    page_id TEXT REFERENCES facebook_pages(id),
    total_renders_ready INTEGER NOT NULL,
    total_renders_failed INTEGER NOT NULL,
    total_published INTEGER NOT NULL,
    storage_used_mb REAL NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
