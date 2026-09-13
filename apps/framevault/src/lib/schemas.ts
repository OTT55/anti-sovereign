import { z } from "zod";

const HANDLE = /^[a-zA-Z0-9_-]+$/;
const SHA256_HEX = /^[0-9a-f]{64}$/i;

export const signupSchema = z.object({
  email: z.string().trim().email(),
  handle: z.string().trim().min(2).max(32).regex(HANDLE),
  displayName: z.string().trim().min(1).max(80),
  password: z.string().min(8).max(200),
});

export const loginSchema = z.object({
  handle: z.string().trim().min(1),
  password: z.string().min(1),
});

export const profileUpdateSchema = z.object({
  headline: z.string().trim().max(140).optional(),
  bio: z.string().trim().max(2000).optional(),
  location: z.string().trim().max(120).optional(),
  availability: z.enum(["open", "selective", "booked"]).optional(),
});

export const skillCreateSchema = z.object({
  skill: z.string().trim().min(1).max(60),
  level: z.enum(["beginner", "intermediate", "advanced", "expert"]),
});

export const provenanceCreateSchema = z.object({
  contentHash: z.string().trim().regex(SHA256_HEX),
  filename: z.string().trim().min(1).max(255),
  title: z.string().trim().max(200).optional(),
  role: z.string().trim().max(120).optional(),
  contributors: z.string().trim().max(500).optional(),
  aiDisclosure: z.string().trim().max(500).optional(),
  source: z.string().trim().max(200).optional(),
});

export const verifyRequestSchema = z.object({
  hash: z.string().trim().regex(SHA256_HEX),
});

export const authenticateRequestSchema = z.object({
  handle: z.string().trim().min(1),
  password: z.string().min(1),
});

export const creditRequestSchema = z.object({
  handle: z.string().trim().min(1),
  kind: z.string().trim().min(1).max(80),
  weight: z.number().int(),
  source: z.string().trim().min(1).max(80),
  amountPence: z.number().int().positive().optional(),
  payerHandle: z.string().trim().min(1).optional(),
  review: z
    .object({
      rating: z.number().int().min(1).max(5),
      body: z.string().trim().max(2000),
    })
    .optional(),
});
