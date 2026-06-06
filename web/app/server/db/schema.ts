import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core'
import { z } from 'zod'

// ── Devices ──
export const devices = sqliteTable('devices', {
  id: text('id').primaryKey(),
  name: text('name').notNull().default('Unnamed'),
  variant: text('variant').notNull(), // 'e1001' | 'e1002'
  firmwareVersion: text('firmware_version'),
  batteryPct: integer('battery_pct'),
  chargeState: text('charge_state'), // 'battery' | 'charging' | 'full'
  lastSeen: integer('last_seen'), // unix timestamp ms
  createdAt: integer('created_at').notNull(),
})

// ── Screen Configurations (templates) ──
export const screens = sqliteTable('screens', {
  id: text('id').primaryKey(), // UUID
  name: text('name').notNull(),
  type: text('type').notNull(), // 'url' | 'html' | 'weather' | 'maintenance'
  config: text('config').notNull(), // JSON blob
  thumbData: text('thumb_data'), // base64 PNG preview
  createdAt: integer('created_at').notNull(),
  updatedAt: integer('updated_at').notNull(),
})

// ── Device ←→ Screen assignments (ordered) ──
export const deviceScreens = sqliteTable('device_screens', {
  id: text('id').primaryKey(), // UUID
  deviceId: text('device_id').notNull().references(() => devices.id),
  screenId: text('screen_id').notNull().references(() => screens.id),
  sortOrder: integer('sort_order').notNull().default(0),
  enabled: integer('enabled').notNull().default(1), // boolean
  refreshInterval: integer('refresh_interval').default(3600), // seconds
})

// ── Zod validation schemas ──
export const deviceSchema = z.object({
  id: z.string().min(1).max(64),
  name: z.string().min(1).max(64).optional(),
  variant: z.enum(['e1001', 'e1002']),
  firmwareVersion: z.string().optional(),
  batteryPct: z.number().int().min(-2).max(100).optional(),
  chargeState: z.enum(['battery', 'charging', 'full']).optional(),
})

export const screenSchema = z.object({
  id: z.string().uuid().optional(), // auto-generated on create
  name: z.string().min(1).max(128),
  type: z.enum(['url', 'html', 'weather', 'maintenance']),
  config: z.record(z.unknown()),
})

export const urlScreenConfig = z.object({
  url: z.string().url(),
  selector: z.string().optional(),
  refreshMinutes: z.number().int().min(5).max(1440).default(60),
})

export const deviceScreenSchema = z.object({
  id: z.string().uuid().optional(),
  deviceId: z.string().min(1),
  screenId: z.string().uuid(),
  sortOrder: z.number().int().min(0).default(0),
  enabled: z.boolean().default(true),
  refreshInterval: z.number().int().min(60).max(86400).default(3600),
})
