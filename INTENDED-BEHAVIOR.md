# INTENDED-BEHAVIOR.md — Design decisions, flows, and expected behavior

> **For AI agents modifying this project.** Do not change behaviors described here without updating this file.
> Architecture overview: [`AI-MAP.md`](AI-MAP.md)

---

## 1. Error Handling Hierarchy

When something goes wrong, the display must show the **most specific and actionable error possible**. The system follows a strict priority:

| Priority | Error Source | What the Device Shows | How |
|---|---|---|---|
| 1 | Flask (server) | Full debug page | Server renders `debug_error.html` as binary, device displays it via `showPage()` |
| 2 | WiFi connection | Pre-rendered local bitmap: "WiFi Connection Failed — Check SSID & password" | `showError(true)` → `showEmbeddedBitmap(error_wifi_*)` |
| 3 | Server unreachable | Pre-rendered local bitmap: "Server Unreachable — Connected to WiFi but server did not respond" | `showError(false)` → `showEmbeddedBitmap(error_fetch_*)` |

### Flow in firmware (`refreshAndShow()`):

```
refreshAndShow(page):
  if !connectWiFi()         → showError(true)  [priority 2]
  if fetchPage() returns -2 → showPage()        [priority 1 — server-rendered debug page]
  if fetchPage() returns -1 → showError(false)  [priority 3]
  if fetchPage() returns 0  → skip (304, unchanged)
  if fetchPage() returns 1  → showPage()        [normal success]
```

### fetchPage error body capture (firmware):

When `fetchPage()` receives a non-200 response:
- Reads the HTTP response body into the pre-allocated framebuffer
- If body is > 100 bytes: returns `-2` (meaningful server-rendered debug page)
- If body is ≤ 100 bytes: discards, returns `-1` (true failure)

### Server debug page (Flask):

When any exception occurs in a device-aware `.bin` route:
- Try/except wraps the entire device-aware code path
- On exception, renders `debug_error.html` with:
  - HTTP status code
  - Full URL attempted
  - Device ID
  - Page number
  - Timestamp
  - Error type + exception message
  - Last ~800 chars of Python traceback
- Returns this as `application/octet-stream` (valid framebuffer) with status 200
- Device displays the debug page directly on the e-ink screen

**No generic 500 response should ever reach the e-ink display.** Flask's `@app.errorhandler(500)` also catches exceptions that escape the try/except and returns a debug page for `.bin` routes.

---

## 2. Device Registration / Onboarding Flow

The server auto-adopts unknown devices. No manual registration step is required.

### Flow:

```
Firmware requests:  GET /dashboard-bw.bin?device=XXXX&page=0&battery=xx
  ↓
Flask receives request:
  get_device("XXXX") → None (not in DB)
  register_device("XXXX", "e1001") → auto-creates in SQLite
  get_device_screens("XXXX") → [] (no screens assigned yet)
  ↓
If DB is unavailable (file missing):
  Raises RuntimeError — rendered as debug error page on e-ink with path info
If DB available but no screens assigned:
  Renders status page with mode="no_screens" showing:
    - Device name + ID (large monospace hex)
    - "NEEDS SCREENS" badge
    - URL to manage screens (auto-detected via X-Forwarded headers or PUBLIC_URL env var)
    - QR code (if qrcode[pil] installed)
    - Instructions: visit URL, assign screens to this device
```

### Registration URL detection priority (`_get_public_url()`):

1. `PUBLIC_URL` env var (explicit override, e.g. `PUBLIC_URL=https://test.oisl.dev`)
2. `X-Forwarded-Host` + `X-Forwarded-Proto` headers (set by Nuxt proxy)
3. `request.host` fallback (direct connection, least reliable)

### Nuxt proxy forwards these headers to Flask:

Every proxied request includes `X-Forwarded-Host` and `X-Forwarded-Proto` so Flask can resolve the public URL.

### After registration:

Once screens are assigned to the device via the web dashboard, `get_device_screens()` returns the screens, and the server renders the assigned screen content instead of the registration page.

---

## 3. Server Architecture & Routing

```
ESP32 / Browser ──→ Nuxt (port 3000) ──→ proxy middleware ──→ Flask (port 8088)
```

### Nuxt handles (Nitro API + DB):

| Path | Purpose |
|---|---|
| `/api/devices` | CRUD for registered devices |
| `/api/screens` | CRUD for screen types/configs |
| `/api/device/:id/page/:n` | Screen assignment lookup (metadata only, not binary) |
| `/` , `/flasher` , `/pages` , `/devices` | Web UI pages |

### Nuxt proxy forwards to Flask:

| Path prefix | Flask handler |
|---|---|
| `/dashboard.bin` | E1002 color framebuffer binary |
| `/dashboard-bw.bin` | E1001 monochrome framebuffer binary |
| `/dashboard.png` | Dithered preview |
| `/dashboard-bw.png` | BW dithered preview |
| `/preview.png` | Full-color preview |
| `/dashboard*` | Legacy dashboard routes |
| `/health` | Health check |
| `/trigger` , `/trigger-e1001` | BLE trigger renders |
| `/demo/*` | Demo pages |
| `/page/*` | URL page binary/preview/meta |
| `/pages` | Page list |
| `/api/page/*` | Page CRUD API |
| `/api/build*` | PlatformIO build backend |
| `/api/prebuilt` | Prebuilt firmware listing |
| `/prebuilt/*` | Prebuilt binary download |

### Flask handles (direct):

All the above paths plus page/pages/build endpoints.

### Database:

- SQLite at `web/.data/eink.db`
- Tables: `devices`, `screens`, `device_screens` (many-to-many with sorting)
- Created by Nuxt Nitro on first startup (`web/server/plugins/db.ts`)
- Flask accesses via `device_db.py` (simple SQLite queries, no ORM)

---

## 4. Firmware: Two Variants, Shared Code

| | E1001 (monochrome) | E1002 (color) |
|---|---|---|
| Board | reTerminal E1001 | reTerminal E1002 |
| Build env | `reterminal_e1001` | `seeed_xiao_esp32s3` |
| Display driver | `GxEPD2_750_GDEY075T7` (BW) | `GxEPD2_730c_GDEP073E01` (7C) |
| FB size | 48,000 bytes | 192,000 bytes |
| Server path | `/dashboard-bw.bin` | `/dashboard.bin` |
| BLE name | `E1001-Dashboard` | `E1002-Dashboard` |
| SPI speed | 2 MHz | 200 kHz |

Key: Both use the same ESP32-S3 + pinout. Differences handled via `#ifdef E1001_VARIANT` / `#ifdef E1002_VARIANT`.

---

## 5. Firmware Error Bitmaps (Local)

Generated by `scripts/generate_embedded_screens.py` at build time. Embedded as `const uint8_t[]` arrays in `embedded_screens.h`.

### Current error screens:

| Bitmap | Text shown | Trigger |
|---|---|---|
| `splash_e1001_bw` / `splash_e1002` | Device name + boot | On first-ever boot (`rtc_first_boot`) |
| `error_wifi_e1001_bw` / `error_wifi_e1002` | "WiFi Connection Failed — Check SSID & password" | `connectWiFi()` fails |
| `error_fetch_e1001_bw` / `error_fetch_e1002` | "Server Unreachable — Connected to WiFi but server did not respond" | WiFi OK but server returns non-200 with no body |

### What to regenerate:

After modifying `error.html` or `splash.html` templates:
```bash
python3 scripts/generate_embedded_screens.py
```
Then rebuild firmware. The `.h` file is checked into git so the build environment doesn't need Playwright.

---

## 6. Device Wake / Sleep Cycle

```
Timer (60s) or Button or BLE Trigger
  ↓
Wake from deep sleep
  ↓
Button wake:    wait for page selection → confirm → refresh → enterUSBAwareSleep()
Timer wake:     BLE advertise 10s for trigger → if triggered → refresh → enterUSBAwareSleep()
Health (6h):    skip BLE → WiFi → fetch → refresh → enterUSBAwareSleep()
  ↓
enterUSBAwareSleep():
  USB connected →   light sleep (5s loop) with LED active, re-check charge state
  No USB →          deep sleep (60s)
```

---

## 7. Caching & Conditional Fetches

Flask returns MD5 ETag headers on all `.bin` responses. The firmware stores ETags in RTC memory (`rtc_etags[3][64]`) across deep sleep cycles and sends `If-None-Match` on subsequent fetches. Server responds 304 Not Modified if content hasn't changed → firmware skips display refresh (saves battery, reduces ghosting).

---

## 8. URL Auto-Detection

The `PUBLIC_URL` env var should be set in production deployments so registration pages, QR codes, and debug screens show correct addresses. Without it, the server falls back to reverse proxy headers, then to the incoming request host (which may be `127.0.0.1` if proxied).

---

## 9. Flash & Build Progress

### Build progress (PlatformIO):
- Indeterminate `<UProgress animation="carousel" />` while building
- Log lines streamed to the console `<pre>` block
- No numeric % during build (PlatformIO doesn't expose it)

### Flash progress (esptool-js):
- Indeterminate carousel before flash begins (`flashStarted = false`)
- Switches to determinate `<UProgress :value="flashProgress" />` on first `reportProgress` callback
- `flashProgress` and `flashStarted` are separate refs to avoid the esptool initial 0% progress being stuck on carousel
- Button label: "Build" (not "Build & Download" — user may flash after building)
