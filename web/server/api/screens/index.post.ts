import { getDb } from '~/server/db/index'
import { screens, screenSchema } from '~/server/db/schema'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)

  const parsed = screenSchema.safeParse(body)
  if (!parsed.success) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid screen data',
      data: parsed.error.flatten()
    })
  }

  const db = getDb()

  const now = Date.now()
  const screen = {
    id: parsed.data.id || crypto.randomUUID(),
    name: parsed.data.name,
    type: parsed.data.type,
    config: JSON.stringify(parsed.data.config),
    thumbData: null,
    createdAt: now,
    updatedAt: now
  }

  db.insert(screens).values(screen).run()

  setResponseStatus(event, 201)
  return {
    ...screen,
    config: parsed.data.config
  }
})
