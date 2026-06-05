import { getDb } from '~/server/db/index'
import { screens, deviceScreens } from '~/server/db/schema'
import { eq } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  if (!id) {
    throw createError({ statusCode: 400, statusMessage: 'Screen ID required' })
  }

  const db = getDb()

  const existing = db.select({ id: screens.id }).from(screens).where(eq(screens.id, id)).get()
  if (!existing) {
    throw createError({ statusCode: 404, statusMessage: 'Screen not found' })
  }

  db.delete(deviceScreens).where(eq(deviceScreens.screenId, id)).run()
  db.delete(screens).where(eq(screens.id, id)).run()

  setResponseStatus(event, 204)
  return null
})
