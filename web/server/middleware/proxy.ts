// Proxy Flask API calls to localhost:8088 in production.
// Zero Ansible changes needed — Nuxt handles all routing.
export default defineEventHandler(async (event) => {
  const url = getRequestURL(event)
  const path = url.pathname

  // Paths handled by Flask (dashboard rendering, builds, weather, pages)
  const FLASK_PREFIXES = [
    '/api/build', '/api/health', '/api/trigger', '/api/trigger-e1001',
    '/api/page', '/api/pages', '/prebuilt', '/dashboard', '/preview.png',
    '/health', '/page', '/pages', '/trigger', '/trigger-e1001', '/demo'
  ]

  if (!FLASK_PREFIXES.some(p => path.startsWith(p))) return

  const flaskUrl = `http://127.0.0.1:8088${url.pathname}${url.search}`
  const method = event.method
  const body = method !== 'GET' && method !== 'HEAD'
    ? await readRawBody(event)
    : undefined

  try {
    const headers: Record<string, string> = {}
    if (body) headers['Content-Type'] = 'application/json'
    // Forward If-None-Match for ETag conditional requests (304 caching)
    const ifNoneMatch = getHeader(event, 'If-None-Match')
    if (ifNoneMatch) headers['If-None-Match'] = ifNoneMatch

    const res = await fetch(flaskUrl, { method, headers, body })
    const ct = res.headers.get('content-type') || 'application/octet-stream'
    const data = ct.includes('image') || ct.includes('octet-stream')
      ? Buffer.from(await res.arrayBuffer())
      : await res.text()

    setResponseStatus(event, res.status)
    setHeader(event, 'Content-Type', ct)
    // Forward ETag for conditional caching
    if (res.headers.get('etag')) setHeader(event, 'ETag', res.headers.get('etag')!)
    return data
  } catch {
    setResponseStatus(event, 502)
    return { error: 'Flask backend unreachable' }
  }
})
