import { z } from "zod";

const SHA256_HEX = /^[0-9a-f]{64}$/i;

export const registerRequestSchema = z.object({
  handle: z
    .string()
    .trim()
    .min(2)
    .max(32)
    .regex(/^[a-zA-Z0-9_-]+$/, "handle may only contain letters, numbers, - and _"),
  displayName: z.string().trim().min(1).max(80),
  fileHash: z.string().trim().regex(SHA256_HEX, "must be a 64-character hex SHA-256 hash"),
  filename: z.string().trim().min(1).max(255),
  description: z.string().trim().max(2000).optional(),
});

export type RegisterRequest = z.infer<typeof registerRequestSchema>;

export const verifyQuerySchema = z.object({
  hash: z.string().trim().regex(SHA256_HEX, "must be a 64-character hex SHA-256 hash"),
});
