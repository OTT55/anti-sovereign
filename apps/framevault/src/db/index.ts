import path from "node:path";
import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "./schema";

const dbPath = process.env.FRAMEVAULT_DB_PATH ?? path.join(process.cwd(), "framevault.sqlite");

const sqlite = new Database(dbPath, { timeout: 15000 });
sqlite.pragma("journal_mode = WAL");
sqlite.pragma("foreign_keys = ON");

export const db = drizzle(sqlite, { schema });
