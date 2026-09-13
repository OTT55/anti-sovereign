import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const users = sqliteTable("users", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  email: text("email").notNull().unique(),
  handle: text("handle").notNull().unique(),
  displayName: text("display_name").notNull(),
  passwordHash: text("password_hash").notNull(),
  verified: integer("verified", { mode: "boolean" }).notNull().default(false),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const creatorProfiles = sqliteTable("creator_profiles", {
  userId: integer("user_id")
    .primaryKey()
    .references(() => users.id),
  headline: text("headline"),
  bio: text("bio"),
  location: text("location"),
  availability: text("availability", { enum: ["open", "selective", "booked"] })
    .notNull()
    .default("open"),
  updatedAt: text("updated_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const profileSkills = sqliteTable("profile_skills", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  userId: integer("user_id")
    .notNull()
    .references(() => users.id),
  skill: text("skill").notNull(),
  level: text("level", { enum: ["beginner", "intermediate", "advanced", "expert"] }).notNull(),
});

export const provenanceRecords = sqliteTable("provenance_records", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  registryId: text("registry_id").notNull().unique(),
  ownerId: integer("owner_id")
    .notNull()
    .references(() => users.id),
  contentHash: text("content_hash").notNull().unique(),
  filename: text("filename").notNull(),
  title: text("title"),
  role: text("role"),
  contributors: text("contributors"),
  aiDisclosure: text("ai_disclosure"),
  source: text("source"),
  signature: text("signature").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const reviews = sqliteTable("reviews", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  subjectUserId: integer("subject_user_id")
    .notNull()
    .references(() => users.id),
  authorName: text("author_name").notNull(),
  authorHandle: text("author_handle"),
  rating: integer("rating").notNull(),
  body: text("body"),
  context: text("context"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const reputationEvents = sqliteTable("reputation_events", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  userId: integer("user_id")
    .notNull()
    .references(() => users.id),
  kind: text("kind").notNull(),
  weight: integer("weight").notNull(),
  source: text("source").notNull(),
  amountPence: integer("amount_pence"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const ledgerSpend = sqliteTable("ledger_spend", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  userId: integer("user_id")
    .notNull()
    .references(() => users.id),
  counterparty: text("counterparty").notNull(),
  kind: text("kind").notNull(),
  source: text("source").notNull(),
  amountPence: integer("amount_pence").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});
