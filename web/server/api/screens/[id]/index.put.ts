import { getDb } from '~/server/db/index'
import { screens, screenSchema } from '~/server/db/schema'
import { eq } from 'drizzle-orm'

const updateSchema = screenSchema.omit({ id: true })

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  if (!id) {
    throw createError({ statusCode: 400, statusMessage: 'Screen ID required' })
  }

  const body = await readBody(event)

  const parsed = updateSchema.safeParse(body)
  if (!parsed.success) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid screen data',
      data: parsed.error.flatten()
    })
  }

  const db = getDb()

  const existing = db.select({ id: screens.id }).from(screens).where(eq(screens.id, id)).get()
  if (!existing) {
    throw createError({ statusCode: 404, statusMessage: 'Screen not found' })
  }

  const updates = {
    name: parsed.data.name,
    type: parsed.data.type,
    config: JSON.stringify(parsed.data.config),
    updatedAt: Date.now()
  }

  db.update(screens).set(updates).where(eq(screens.id, id)).run()

  const updated = db.select().from(screens).where(eq(screens.id, id)).get()!
  return {
    ...updated,
    config: parsed.data.config
  }
})
