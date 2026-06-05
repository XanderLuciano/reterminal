import { getDb } from '~/server/db/index'
import { devices, deviceScreens, screens } from '~/server/db/schema'
import { eq, and, asc } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const deviceId = getRouterParam(event, 'id')
  const pageN = getRouterParam(event, 'n')

  if (!deviceId || !pageN) {
    throw createError({ statusCode: 400, statusMessage: 'Device ID and page number required' })
  }

  const n = parseInt(pageN, 10)
  if (isNaN(n) || n < 0) {
    throw createError({ statusCode: 400, statusMessage: 'Invalid page number' })
  }

  const db = getDb()

  const device = db.select().from(devices).where(eq(devices.id, deviceId)).get()
  if (!device) {
    throw createError({ statusCode: 404, statusMessage: 'Device not found' })
  }

  const assignments = db
    .select({
      screen: screens,
      sortOrder: deviceScreens.sortOrder,
      enabled: deviceScreens.enabled,
      refreshInterval: deviceScreens.refreshInterval
    })
    .from(deviceScreens)
    .innerJoin(screens, eq(deviceScreens.screenId, screens.id))
    .where(and(eq(deviceScreens.deviceId, deviceId), eq(deviceScreens.enabled, 1)))
    .orderBy(asc(deviceScreens.sortOrder))
    .all()

  if (assignments.length === 0) {
    throw createError({ statusCode: 404, statusMessage: 'No screens assigned to this device' })
  }

  // Cycle through screens: page N wraps around
  const idx = n % assignments.length
  const assignment = assignments[idx]

  const config = JSON.parse(assignment.screen.config)

  // Update device last_seen
  db.update(devices)
    .set({ lastSeen: Date.now() })
    .where(eq(devices.id, deviceId))
    .run()

  return {
    deviceId,
    page: n,
    totalScreens: assignments.length,
    screenIndex: idx,
    screen: {
      id: assignment.screen.id,
      name: assignment.screen.name,
      type: assignment.screen.type,
      config,
      refreshInterval: assignment.refreshInterval
    }
  }
})
