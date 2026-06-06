import { getDb } from '~/server/db/index'

export default defineNitroPlugin(() => {
  getDb()
  console.log('[db] SQLite database initialized')
})
