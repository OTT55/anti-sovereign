import { sql } from "drizzle-orm";
import { index, integer, sqliteTable, text, unique } from "drizzle-orm/sqlite-core";

export const creators = sqliteTable("creators", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  handle: text("handle").notNull().unique(),
  displayName: text("display_name").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});

export const registrations = sqliteTable(
  "registrations",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    registryId: text("registry_id").notNull().unique(),
    creatorId: integer("creator_id")
      .notNull()
      .references(() => creators.id),
    filename: text("filename").notNull(),
    fileHash: text("file_hash").notNull().unique(),
    description: text("description"),
    leafIndex: integer("leaf_index").notNull(),
    signature: text("signature").notNull(),
    tsaServer: text("tsa_server"),
    tsaGrantedAt: text("tsa_granted_at"),
    tsaToken: text("tsa_token"),
    tsaStatus: text("tsa_status", { enum: ["granted", "unavailable"] }).notNull(),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
  },
  (table) => [
    index("idx_registrations_creator").on(table.creatorId),
    unique("uq_registrations_leaf_index").on(table.leafIndex),
  ],
);

export const merkleCheckpoints = sqliteTable("merkle_checkpoints", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  leafCount: integer("leaf_count").notNull(),
  merkleRoot: text("merkle_root").notNull(),
  signature: text("signature").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(strftime('%Y-%m-%dT%H:%M:%fZ','now'))`),
});
