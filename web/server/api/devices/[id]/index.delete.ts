import { getDb } from '~/server/db/index'
import { devices, deviceScreens } from '~/server/db/schema'
import { eq } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  if (!id) {
    throw createError({ statusCode: 400, statusMessage: 'Device ID required' })
  }

  const db = getDb()

  const existing = db.select({ id: devices.id }).from(devices).where(eq(devices.id, id)).get()
  if (!existing) {
    throw createError({ statusCode: 404, statusMessage: 'Device not found' })
  }

  db.delete(deviceScreens).where(eq(deviceScreens.deviceId, id)).run()
  db.delete(devices).where(eq(devices.id, id)).run()

  setResponseStatus(event, 204)
  return null
})
