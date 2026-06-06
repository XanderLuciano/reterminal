# E1001 + E1002 ePaper Dashboards — Wireless

> **🚀 Just got here?** [`QUICKSTART.md`](QUICKSTART.md) — zero to working display in ~10 minutes.

> **🤖 Point your AI here** — copy-paste this into Claude, ChatGPT, or any AI assistant:
>
> ```
> You're working with the reTerminal ePaper Dashboard project from github.com/XanderLuciano/reterminal.
>
> 1. Read QUICKSTART.md — step-by-step setup instructions
> 2. Read AI-MAP.md — routing rules, gotchas, and architecture
> 3. Read web/.ai/OVERVIEW.md — web app architecture, DB design, API routes
> 4. Read web/.ai/AGENT-WORKFLOW.md — reusable multi-agent build workflow
> 5. Two displays: E1001 (monochrome, env reterminal_e1001) and E1002 (color, env seeed_xiao_esp32s3)
>
> My goal is: [describe what you need]
> ```

Two wireless e-ink dashboards sharing one codebase. Flask renders pages, Nuxt 4 powers the web UI, displays fetch over WiFi.

## Architecture

```
Browser → Nuxt:3000 (web UI, devices/screens API)
              └─ proxy → Flask:8088 (dashboard rendering, builds, BLE)
ESP32  → Nuxt:3000 (firmware fetch, device registration)
```

- **Nuxt 4 + NuxtUI** — web dashboard at `:3000` (flasher, device manager, screen builder)
- **Flask** — dashboard rendering at `:8088` (Jinja2 → Playwright → e-ink binary)
- **SQLite + Drizzle** — device/screen management database

## Hardware

| | E1002 | E1001 |
|---|---|---|
| **Display** | 7.3" Spectra 6 color | 7.5" monochrome BW |
| **Resolution** | 800×480 | 800×480 |
| **Colors** | 6 | 2 |
| **MCU** | ESP32-S3, 8MB PSRAM | ESP32-S3, 8MB PSRAM |

## Pages (on display)

- **Page 1 — The Daily Glitch** — newspaper layout
- **Page 2 — Weather** — NWS live data
- **Page 3 — Maintenance** — home maintenance tracker

## Web UI (`http://localhost:3000`)

| Route | Page |
|---|---|
| `/` | Homepage — project overview |
| `/flasher` | Web flasher — configure WiFi, build & flash firmware |
| `/pages` | Page manager — URL page previews with thumbnails |
| `/devices` | Device registry — register, view battery/status |
| `/screens` | Screen builder — create screen configs |
| `/device-screens` | Assign screens to devices |

## Server Endpoints

### Flask (`:8088`) — dashboard rendering
| Endpoint | Description |
|---|---|
| `GET /dashboard.bin?template=name&battery=pct` | E1002 color framebuffer (192KB) |
| `GET /dashboard-bw.bin?template=name&battery=pct` | E1001 BW framebuffer (48KB) |
| `GET /trigger` / `/trigger-e1001` | BLE wake trigger |
| `GET /page/<name>.bin` / `.png` | URL page rendering |
| `POST/PUT/DELETE /page/<name>` | Page CRUD |

### Nuxt Nitro (`:3000`) — device/screen management
| Endpoint | Description |
|---|---|
| `GET/POST /api/devices` | Device CRUD |
| `GET/POST /api/screens` | Screen CRUD |
| `POST /api/devices/:id/screens` | Assign screens to device |
| `GET /api/device/:id/page/:n` | Per-device page binary |

Full API reference: `web/.ai/API.md`

## Quick Setup

### 🐳 Docker (both services in one container)

```bash
git clone https://github.com/XanderLuciano/reterminal.git
cd reterminal
docker compose up -d
# → Nuxt UI at http://localhost:3000
# → Flask API at http://localhost:8088
```

### 📦 Manual

```bash
# Server
pip install -r requirements.txt && playwright install chromium

# Web UI
cd web && npm install && npm run build

# Run both (or use PM2)
python3 server/server.py &    # Flask :8088
cd web && node .output/server/index.mjs  # Nuxt :3000
```

### PM2 (production)

```bash
pm2 start ecosystem.config.js --only epaper-server,epaper-web
```

## First-Time Setup (after flashing)

1. **Flash the display** — use the [web flasher](http://localhost:3000/flasher) or PlatformIO CLI
2. **Display boots** → shows splash screen → fetches first page
3. **Auto-registration** — the display sends its unique ID (generated from hardware MAC + chip ID). The server auto-registers it with a default name.
4. **If no screens assigned** → the display shows a registration page with its device ID and a QR code:

```
┌─────────────────────────────────────────┬──────────┐
│  Device Not Registered                  │  ██▄▄██  │
│  Your display needs to be registered    │  ██████  │
│  before it can show custom screens.     │  ██▄▄██  │
│                                         │          │
│  ┌──────────────────────┐              │  QR code │
│  │      A1B2C3D4        │              │  → scan  │
│  └──────────────────────┘              │  to reg  │
│                                         │          │
│  1. Go to http://server:3000/devices   │          │
│  2. Enter the device ID shown above     │          │
│  3. Assign screens to this display      │          │
└─────────────────────────────────────────┴──────────┘
```

5. **Scan the QR code** → opens `/devices?register=A1B2C3D4` with the ID pre-filled
6. **Register** → give it a friendly name (e.g. "Living Room")
7. **Assign screens** → go to `/device-screens`, pick the device, choose which screens to show
8. **Next refresh** → the display fetches its assigned screens automatically

> 💡 **Auto-adopt:** If you don't assign screens, the display shows the registration page on every refresh — a constant reminder to set it up. Once screens are assigned, they cycle through automatically.

## Project Layout

```
├── README.md / QUICKSTART.md / AI-MAP.md / HARDWARE.md
├── Dockerfile / docker-compose.yml
├── requirements.txt
├── server/                    # Flask dashboard renderer
│   ├── server.py              # Routes, ETag caching
│   ├── renderer.py            # HTML→PNG→dither→pack_bits
│   ├── weather_provider.py    # NWS weather (free API)
│   └── templates/             # Jinja2 HTML (800×480)
├── web/                       # Nuxt 4 web dashboard
│   ├── app/                   # Vue pages, DB schema
│   │   ├── pages/             # flasher, devices, screens, pages
│   │   └── server/db/         # Drizzle ORM + SQLite
│   ├── server/                # Nitro API routes + proxy middleware
│   │   ├── api/               # devices, screens, device/:id/page
│   │   └── middleware/        # Flask proxy
│   └── .ai/                   # AI-readable docs
├── flasher/                   # Build handler + prebuilt binaries
│   ├── build_handler.py       # PlatformIO build backend
│   └── prebuilt/              # Factory firmware binaries
└── firmware/                  # ESP32-S3 (PlatformIO)
    ├── src/main.cpp
    └── platformio.ini
```

## Key Facts

- Flask + Nuxt in one Docker container (multi-stage build)
- Nuxt proxies Flask API calls — zero Ansible changes for existing deploy
- ETag caching on dashboard binaries (304 Not Modified when unchanged)
- Image persists with zero power (e-ink)
- Auto-refresh every 6 hours prevents ghosting
- E1002 color refresh: 25-45s. E1001 BW: ~5s
- Battery life: 3-4 weeks (2000mAh)
