import { getDb } from '~/server/db/index'
import { screens } from '~/server/db/schema'
import { eq } from 'drizzle-orm'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  if (!id) {
    throw createError({ statusCode: 400, statusMessage: 'Screen ID required' })
  }

  const db = getDb()

  const screen = db.select().from(screens).where(eq(screens.id, id)).get()
  if (!screen) {
    throw createError({ statusCode: 404, statusMessage: 'Screen not found' })
  }

  return {
    ...screen,
    config: JSON.parse(screen.config)
  }
})
