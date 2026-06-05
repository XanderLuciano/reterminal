import { getDb } from '~/server/db/index'
import { devices, deviceScreens } from '~/server/db/schema'
import { eq, sql } from 'drizzle-orm'

export default defineEventHandler(async () => {
  const db = getDb()

  const result = db
    .select({
      id: devices.id,
      name: devices.name,
      variant: devices.variant,
      firmwareVersion: devices.firmwareVersion,
      batteryPct: devices.batteryPct,
      chargeState: devices.chargeState,
      lastSeen: devices.lastSeen,
      createdAt: devices.createdAt,
      screenCount: sql<number>`COUNT(${deviceScreens.id})`
    })
    .from(devices)
    .leftJoin(deviceScreens, eq(devices.id, deviceScreens.deviceId))
    .groupBy(devices.id)
    .all()

  return result.map(d => ({
    ...d,
    screenCount: Number(d.screenCount)
  }))
})
