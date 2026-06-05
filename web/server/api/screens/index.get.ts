import { getDb } from '~/server/db/index'
import { screens } from '~/server/db/schema'

export default defineEventHandler(async () => {
  const db = getDb()

  const result = db.select().from(screens).all()

  return result.map(s => ({
    ...s,
    config: JSON.parse(s.config)
  }))
})
