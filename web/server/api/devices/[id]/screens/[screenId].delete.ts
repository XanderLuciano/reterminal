import { getDb } from '~/server/db/index'
import { devices, deviceScreens } from '~/server/db/schema'
import { eq, and } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const deviceId = getRouterParam(event, 'id')
  const screenId = getRouterParam(event, 'screenId')

  if (!deviceId || !screenId) {
    throw createError({ statusCode: 400, statusMessage: 'Device ID and Screen ID required' })
  }

  const db = getDb()

  const device = db.select({ id: devices.id }).from(devices).where(eq(devices.id, deviceId)).get()
  if (!device) {
    throw createError({ statusCode: 404, statusMessage: 'Device not found' })
  }

  const assignment = db
    .select({ id: deviceScreens.id })
    .from(deviceScreens)
    .where(and(eq(deviceScreens.deviceId, deviceId), eq(deviceScreens.screenId, screenId)))
    .get()

  if (!assignment) {
    throw createError({ statusCode: 404, statusMessage: 'Screen assignment not found' })
  }

  db.delete(deviceScreens).where(eq(deviceScreens.id, assignment.id)).run()

  setResponseStatus(event, 204)
  return null
})
