import { getDb } from '~/server/db/index'
import { devices, deviceSchema } from '~/server/db/schema'
import { eq } from 'drizzle-orm'
import { z } from 'zod'

const patchSchema = deviceSchema.pick({
  name: true,
  firmwareVersion: true,
  batteryPct: true,
  chargeState: true
}).partial()

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  if (!id) {
    throw createError({ statusCode: 400, statusMessage: 'Device ID required' })
  }

  const body = await readBody(event)

  const parsed = patchSchema.safeParse(body)
  if (!parsed.success) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid update data',
      data: parsed.error.flatten()
    })
  }

  const db = getDb()

  const existing = db.select().from(devices).where(eq(devices.id, id)).get()
  if (!existing) {
    throw createError({ statusCode: 404, statusMessage: 'Device not found' })
  }

  const updates: Record<string, unknown> = {}
  if (parsed.data.name !== undefined) updates.name = parsed.data.name
  if (parsed.data.firmwareVersion !== undefined) updates.firmwareVersion = parsed.data.firmwareVersion
  if (parsed.data.batteryPct !== undefined) updates.batteryPct = parsed.data.batteryPct
  if (parsed.data.chargeState !== undefined) updates.chargeState = parsed.data.chargeState

  if (Object.keys(updates).length > 0) {
    updates.lastSeen = Date.now()
  }

  if (Object.keys(updates).length === 0) {
    throw createError({ statusCode: 400, statusMessage: 'No fields to update' })
  }

  db.update(devices).set(updates).where(eq(devices.id, id)).run()

  const updated = db.select().from(devices).where(eq(devices.id, id)).get()
  return updated
})
