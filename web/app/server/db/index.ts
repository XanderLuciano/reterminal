import Database from 'better-sqlite3'
import { drizzle } from 'drizzle-orm/better-sqlite3'
import * as schema from './schema'
import fs from 'node:fs'
import path from 'node:path'

const DB_DIR = path.resolve(process.cwd(), '.data')
const DB_PATH = path.join(DB_DIR, 'eink.db')

let _db: ReturnType<typeof drizzle> | null = null

export function getDb() {
  if (!_db) {
    fs.mkdirSync(DB_DIR, { recursive: true })
    const sqlite = new Database(DB_PATH)
    sqlite.pragma('journal_mode = WAL')
    sqlite.pragma('foreign_keys = ON')
    _db = drizzle(sqlite, { schema })
    initTables(sqlite)
  }
  return _db
}

function initTables(sqlite: Database.Database) {
  const tablesCreated = sqlite.exec(`
    CREATE TABLE IF NOT EXISTS devices (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL DEFAULT 'Unnamed',
      variant TEXT NOT NULL,
      firmware_version TEXT,
      battery_pct INTEGER,
      charge_state TEXT,
      last_seen INTEGER,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS screens (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      type TEXT NOT NULL,
      config TEXT NOT NULL,
      thumb_data TEXT,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS device_screens (
      id TEXT PRIMARY KEY,
      device_id TEXT NOT NULL REFERENCES devices(id),
      screen_id TEXT NOT NULL REFERENCES screens(id),
      sort_order INTEGER NOT NULL DEFAULT 0,
      enabled INTEGER NOT NULL DEFAULT 1,
      refresh_interval INTEGER DEFAULT 21600
    );
    CREATE INDEX IF NOT EXISTS idx_device_screens_device ON device_screens(device_id);
    CREATE INDEX IF NOT EXISTS idx_device_screens_screen ON device_screens(screen_id);
  `)

  // Seed default screens if none exist
  const existing = sqlite.prepare('SELECT count(*) as cnt FROM screens').get() as { cnt: number }
  if (existing && existing.cnt === 0) {
    const now = Date.now()
    const uuid = crypto.randomUUID()
    sqlite.prepare(
      `INSERT INTO screens (id, name, type, config, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?)`
    ).run(uuid, 'Weather', 'weather', '{}', now, now)
  }
}
