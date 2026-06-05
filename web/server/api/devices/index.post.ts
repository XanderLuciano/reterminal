import { getDb } from '~/server/db/index'
import { devices, deviceSchema } from '~/server/db/schema'
import { eq } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)

  const parsed = deviceSchema.safeParse(body)
  if (!parsed.success) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid device data',
      data: parsed.error.flatten()
    })
  }

  const db = getDb()

  const existing = db.select({ id: devices.id }).from(devices).where(eq(devices.id, parsed.data.id)).get()
  if (existing) {
    throw createError({
      statusCode: 409,
      statusMessage: `Device with ID '${parsed.data.id}' already exists`
    })
  }

  const now = Date.now()
  const device = {
    id: parsed.data.id,
    name: parsed.data.name || 'Unnamed',
    variant: parsed.data.variant,
    firmwareVersion: parsed.data.firmwareVersion || null,
    batteryPct: parsed.data.batteryPct ?? null,
    chargeState: parsed.data.chargeState || null,
    lastSeen: now,
    createdAt: now
  }

  db.insert(devices).values(device).run()

  setResponseStatus(event, 201)
  return device
})
