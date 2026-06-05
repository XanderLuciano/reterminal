import { getDb } from '~/server/db/index'
import { devices, screens, deviceScreens } from '~/server/db/schema'
import { eq, and, asc } from 'drizzle-orm'

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

  const result = db
    .select({
      assignmentId: deviceScreens.id,
      deviceId: deviceScreens.deviceId,
      screenId: deviceScreens.screenId,
      sortOrder: deviceScreens.sortOrder,
      enabled: deviceScreens.enabled,
      refreshInterval: deviceScreens.refreshInterval,
      screenName: screens.name,
      screenType: screens.type,
      screenConfig: screens.config
    })
    .from(deviceScreens)
    .innerJoin(screens, eq(deviceScreens.screenId, screens.id))
    .where(eq(deviceScreens.deviceId, deviceId))
    .orderBy(asc(deviceScreens.sortOrder))
    .all()

  return result.map(r => ({
    assignmentId: r.assignmentId,
    deviceId: r.deviceId,
    screenId: r.screenId,
    sortOrder: r.sortOrder,
    enabled: Boolean(r.enabled),
    refreshInterval: r.refreshInterval,
    screen: {
      name: r.screenName,
      type: r.screenType,
      config: JSON.parse(r.screenConfig)
    }
  }))
})
