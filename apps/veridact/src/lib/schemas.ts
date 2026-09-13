import { z } from "zod";

const SHA256_HEX = /^[0-9a-f]{64}$/i;
const HANDLE = /^[a-zA-Z0-9_-]+$/;

export const enrollRequestSchema = z.object({
  handle: z.string().trim().min(2).max(32).regex(HANDLE),
  publicKeySpki: z.string().trim().min(1),
});

export const attestRequestSchema = z.object({
  handle: z.string().trim().min(2).max(32).regex(HANDLE),
  manifestId: z.string().trim().regex(/^VD-[0-9A-F]{8}$/),
  challenge: z.string().trim().regex(/^[0-9a-f]{32}$/),
  mediaHash: z.string().trim().regex(SHA256_HEX),
  capturedAt: z.string().trim().datetime(),
  signature: z.string().trim().min(1),
  label: z.string().trim().max(200).optional(),
  watermarkSecret: z
    .string()
    .trim()
    .regex(/^[0-9a-f]{14}$/)
    .optional(),
});

export const rushRegisterSchema = z.object({
  production: z.string().trim().min(1).max(200),
  rollNumber: z.string().trim().max(50).optional(),
  sceneTake: z.string().trim().max(50).optional(),
  fileName: z.string().trim().min(1).max(255),
  mediaHash: z.string().trim().regex(SHA256_HEX),
  framerate: z.string().trim().max(20).optional(),
  ditNotes: z.string().trim().max(2000).optional(),
  capturedAt: z.string().trim().datetime(),
});

export const verifyQuerySchema = z.object({
  hash: z.string().trim().regex(SHA256_HEX).optional(),
  manifestId: z.string().trim().optional(),
});
