import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const devices = sqliteTable("devices", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  handle: text("handle").notNull().unique(),
  /** Base64 SPKI DER-encoded ECDSA P-256 public key. The private key never leaves the device. */
  publicKeySpki: text("public_key_spki").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const captureChallenges = sqliteTable("capture_challenges", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  nonce: text("nonce").notNull().unique(),
  issuedAt: text("issued_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
  expiresAt: text("expires_at").notNull(),
  usedAt: text("used_at"),
});

export const manifests = sqliteTable("manifests", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  manifestId: text("manifest_id").notNull().unique(),
  deviceId: integer("device_id")
    .notNull()
    .references(() => devices.id),
  mediaHash: text("media_hash").notNull(),
  label: text("label"),
  challenge: text("challenge").notNull(),
  /** Base64 raw (r||s / IEEE P1363) ECDSA signature, as produced by Web Crypto. */
  signature: text("signature").notNull(),
  capturedAt: text("captured_at").notNull(),
  receivedAt: text("received_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
  /** Hex secret embedded into the pixels at capture time, if watermarking was used. */
  watermarkSecret: text("watermark_secret"),
});

export const filmRushes = sqliteTable("film_rushes", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  rushId: text("rush_id").notNull().unique(),
  deviceId: integer("device_id").references(() => devices.id),
  production: text("production").notNull(),
  rollNumber: text("roll_number"),
  sceneTake: text("scene_take"),
  fileName: text("file_name").notNull(),
  mediaHash: text("media_hash").notNull(),
  framerate: text("framerate"),
  ditNotes: text("dit_notes"),
  capturedAt: text("captured_at").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});
