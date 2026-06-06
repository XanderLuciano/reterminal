# Quick Start — Zero to Working Display

Step-by-step from `git clone` to a wireless e-ink dashboard. ~10 minutes.

> **🤖 Copy-paste this into any AI:**
>
> ```
> You're working with github.com/XanderLuciano/reterminal — an open-source ePaper dashboard project.
> 1. Read this QUICKSTART.md and follow the steps in order
> 2. Read AI-MAP.md for architecture, gotchas, and routing rules
> 3. Read web/.ai/OVERVIEW.md for web app architecture and API routes
> 4. Two display variants: E1001 (BW, env reterminal_e1001) and E1002 (color, env seeed_xiao_esp32s3)
> 5. My goal is: [describe what you need]
> ```

## Prerequisites

- reTerminal E1001 (monochrome) or E1002 (color)
- USB-C cable for flashing
- Docker (recommended) or Python 3.11+ + Node.js 22+

## 1. Clone

```bash
git clone https://github.com/XanderLuciano/reterminal.git
cd reterminal
```

## 2. Start the Server & Web UI

### 🐳 Docker (recommended — both services)

```bash
docker compose up -d
# → Nuxt web UI: http://localhost:3000
# → Flask API:   http://localhost:8088
```

One container, two services. Flask renders dashboards, Nuxt serves the web UI and proxies API calls.

### 📦 Manual

```bash
# Flask server
pip install -r requirements.txt
playwright install chromium

# Nuxt web UI
cd web && npm install && npm run build

# Run both
python3 server/server.py &                           # Flask :8088
cd web && node .output/server/index.mjs             # Nuxt :3000
```

Verify: `curl http://localhost:8088/health` → `{"status":"ok"}`

## 3. Flash the Display

Open `http://localhost:3000/flasher` in Chrome or Edge.

1. Select your display (E1001 or E1002)
2. Enter WiFi SSID, password, and server URL
3. Configure sleep timing (defaults work fine)
4. Click **Build & Download** to get firmware
5. Flash with: `esptool.py --port /dev/ttyUSB0 write_flash 0x0 firmware.bin`

Or build manually:

```bash
cd firmware
cp src/wifi_config.h.example src/wifi_config.h  # edit WiFi creds
# Edit DASHBOARD_BASE_URL in src/main.cpp to your server URL

pio run -e reterminal_e1001 -t upload --upload-port /dev/ttyUSB0   # E1001
pio run -e seeed_xiao_esp32s3 -t upload --upload-port /dev/ttyUSB0 # E1002
```

The display boots, shows splash screen, fetches page 1, then sleeps.

## 4. Use the Display

- **Press any button** to wake — Left/Right to switch pages, Green to confirm
- **BLE trigger:** open `/flasher`, click "Connect & Trigger" to force a refresh
- **30-second timeout** returns to sleep
- **Beeps** indicate current page (1 beep = page 1, etc.)

## 5. Manage via Web UI

```
http://localhost:3000/
```

| Page | What you can do |
|---|---|
| `Flasher` | Configure WiFi, build custom firmware, BLE triggers |
| `Pages` | View URL page previews with thumbnails |
| `Devices` | Register displays, monitor battery and status |
| `Screens` | Create and edit screen configurations |
| `Device Screens` | Assign screens to specific devices |

## 6. Customize Pages

### Edit HTML templates (content)
- `server/templates/newspaper.html` — newspaper layout
- `server/templates/weather.html` — weather dashboard
- `server/templates/maintenance.html` — maintenance tracker
- Edit `server/server.py` → `get_mock_context()` for data
- Restart Flask to see changes

### Add a URL page
1. Open `http://localhost:3000/pages`
2. Click "+ New Page"
3. Enter a name and URL — the server screenshots it at 800×480
4. Add the page name to `TEMPLATE_NAMES[]` in `firmware/src/main.cpp`
5. Update `NUM_PAGES` and reflash

### Live weather location
Edit `server/weather_provider.py` — update `LAT`, `LNG`, and NWS grid point.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Display won't wake | Check power switch on back |
| BLE trigger not working | Wait for 60s timer wake, or press a button |
| Garbled/inverted display | BW display getting color data — check build target |
| 502 on deploy | `pip install flask-cors` — missing from requirements |
| Buttons don't respond | Press and hold for 1 second |
| Server errors | `docker compose logs -f` |
