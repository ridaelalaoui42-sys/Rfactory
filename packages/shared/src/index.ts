import { z } from 'zod';

export const RenderStatusEnum = z.enum([
  'DRAFT',
  'QUEUED',
  'RENDERING',
  'QA',
  'READY',
  'FAILED',
  'CANCELLED',
]);

export const PublishStatusEnum = z.enum([
  'DRAFT',
  'APPROVED',
  'SCHEDULED',
  'UPLOADING',
  'SUBMITTING',
  'VERIFYING',
  'PUBLISHED',
  'NEEDS_LOGIN',
  'BLOCKED',
  'FAILED',
  'UNKNOWN_RESULT',
]);

export const FailureTaxonomyEnum = z.enum([
  'SESSION_EXPIRED',
  'PAGE_NOT_FOUND',
  'WRONG_PAGE',
  'UPLOAD_FAILED',
  'UI_CHANGED',
  'CAPTCHA_REQUIRED',
  'POLICY_BLOCKED',
  'UNKNOWN_RESULT',
  'PUBLISHED',
]);

export const TemplateIdEnum = z.enum(['OUTLINE_MATCH', 'MISSING_PIECE_SLIDE']);

export const RenderConfigSchema = z.object({
  jobId: z.string(),
  templateId: TemplateIdEnum,
  species: z.string(),
  seed: z.number().int().default(1001),
  width: z.number().int().default(1080),
  height: z.number().int().default(1920),
  fps: z.number().int().default(30),
  durationSec: z.number().min(12).max(20).default(15),
  backgroundHex: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default('#F2FAFF'),
  objectCount: z.number().int().min(3).max(8).default(5),
  offsetDistancePx: z.number().min(60).max(260).default(165),
  easeType: z.enum(['easeInOutSine', 'easeInOutCubic', 'linear']).default('easeInOutSine'),
  cycles: z.number().int().min(2).max(8).default(5),
  holdRatio: z.number().min(0.05).max(0.30).default(0.14),
  sliceXRatio: z.tuple([z.number(), z.number()]).default([0.27, 0.51]),
  direction: z.enum(['top_to_bottom', 'bottom_to_top', 'oscillate']).default('top_to_bottom'),
  enableAudio: z.boolean().default(true),
});

export type RenderConfigDTO = z.infer<typeof RenderConfigSchema>;
