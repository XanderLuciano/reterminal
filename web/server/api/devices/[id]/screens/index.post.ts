import { getDb } from '~/server/db/index'
import { devices, deviceScreens, deviceScreenSchema } from '~/server/db/schema'
import { eq, and } from 'drizzle-orm'
import { z } from 'zod'

const bulkAssignSchema = z.object({
  screens: z.array(z.object({
    screenId: z.string().uuid(),
    sortOrder: z.number().int().min(0).default(0),
    enabled: z.boolean().default(true),
    refreshInterval: z.number().int().min(1).max(168).default(6) // hours
  })).min(1).max(50)
})

export default defineEventHandler(async (event) => {
  const deviceId = getRouterParam(event, 'id')
  if (!deviceId) {
    throw createError({ statusCode: 400, statusMessage: 'Device ID required' })
  }

  const db = getDb()

  const device = db.select({ id: devices.id }).from(devices).where(eq(devices.id, deviceId)).get()
  if (!device) {
    throw createError({ statusCode: 404, statusMessage: 'Device not found' })
  }

  const body = await readBody(event)
  const parsed = bulkAssignSchema.safeParse(body)
  if (!parsed.success) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid assignment data',
      data: parsed.error.flatten()
    })
  }

  // Clear existing assignments for this device
  db.delete(deviceScreens).where(eq(deviceScreens.deviceId, deviceId)).run()

  // Insert new assignments
  const now = Date.now()
  const assignments = parsed.data.screens.map(s => ({
    id: crypto.randomUUID(),
    deviceId,
    screenId: s.screenId,
    sortOrder: s.sortOrder,
    enabled: s.enabled ? 1 : 0,
    refreshInterval: s.refreshInterval
  }))

  if (assignments.length > 0) {
    db.insert(deviceScreens).values(assignments).run()
  }

  setResponseStatus(event, 201)
  return { assigned: assignments.length }
})
