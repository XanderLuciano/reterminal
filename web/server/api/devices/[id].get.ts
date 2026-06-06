import { getDb } from '~/server/db/index'
import { devices, screens, deviceScreens } from '~/server/db/schema'
import { eq, and, asc } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  if (!id) {
    throw createError({ statusCode: 400, statusMessage: 'Device ID required' })
  }

  const db = getDb()

  const device = db.select().from(devices).where(eq(devices.id, id)).get()
  if (!device) {
    throw createError({ statusCode: 404, statusMessage: 'Device not found' })
  }

  const assigned = db
    .select({
      assignmentId: deviceScreens.id,
      sortOrder: deviceScreens.sortOrder,
      enabled: deviceScreens.enabled,
      refreshInterval: deviceScreens.refreshInterval,
      screen: screens
    })
    .from(deviceScreens)
    .innerJoin(screens, eq(deviceScreens.screenId, screens.id))
    .where(eq(deviceScreens.deviceId, id))
    .orderBy(asc(deviceScreens.sortOrder))
    .all()

  return {
    ...device,
    assignedScreens: assigned.map(a => ({
      assignmentId: a.assignmentId,
      sortOrder: a.sortOrder,
      enabled: Boolean(a.enabled),
      refreshInterval: a.refreshInterval,
      ...a.screen
    }))
  }
})
