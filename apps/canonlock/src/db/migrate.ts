import path from "node:path";
import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import { migrate } from "drizzle-orm/better-sqlite3/migrator";

const dbPath = process.env.CANONLOCK_DB_PATH ?? path.join(process.cwd(), "canonlock.sqlite");

const sqlite = new Database(dbPath);
const db = drizzle(sqlite);

migrate(db, { migrationsFolder: path.join(process.cwd(), "drizzle") });

console.log(`Canonlock database migrated at ${dbPath}`);
sqlite.close();
