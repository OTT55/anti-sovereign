import path from "node:path";
import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "./schema";

const dbPath = process.env.CANONLOCK_DB_PATH ?? path.join(process.cwd(), "canonlock.sqlite");

// Next.js's build-time page-data collection can import this module from
// several workers concurrently, each opening their own connection to the
// same file — `timeout` makes better-sqlite3 wait for the lock on open
// itself, not just on later queries, instead of failing immediately.
const sqlite = new Database(dbPath, { timeout: 5000 });
sqlite.pragma("journal_mode = WAL");
sqlite.pragma("foreign_keys = ON");

export const db = drizzle(sqlite, { schema });
