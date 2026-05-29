# Quick Start — Zero to Working ePaper Dashboard

This guide gets you from `git clone` to a working wireless e-ink display in ~10 minutes. Designed for both humans and AI agents.

## Prerequisites

**You need:**
- A reTerminal E1001 (monochrome) or E1002 (color)
- USB-C cable for flashing
- Linux/macOS machine with WiFi and Bluetooth

**Software to install:**

```bash
# PlatformIO CLI (firmware builds)
curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -o get-platformio.py
python3 get-platformio.py

# Python dependencies (server)
pip install -r requirements.txt

# Playwright browser (for HTML→PNG rendering)
playwright install chromium
```

## 1. Clone

```bash
git clone https://github.com/XanderLuciano/reterminal.git
cd reterminal
```

## 2. Configure

### WiFi credentials
```bash
cp firmware/src/wifi_config.h.example firmware/src/wifi_config.h
```
Edit `firmware/src/wifi_config.h` — set your WiFi SSID and password.

### Server IP
Edit `firmware/src/main.cpp` — change `DASHBOARD_BASE_URL` to your server's IP:
```cpp
const char* DASHBOARD_BASE_URL = "http://YOUR_SERVER_IP:8088/dashboard.bin";       // E1002
const char* DASHBOARD_BASE_URL = "http://YOUR_SERVER_IP:8088/dashboard-bw.bin";    // E1001
```

### Weather location (optional)
Edit `server/weather_provider.py` — update `GRID_ID`, `GRID_X`, `GRID_Y` to your NWS grid point, and the lat/lng in the sunrise/open-meteo URLs.

## 3. Start the Server

```bash
cd server
python3 server.py
# Server listening on http://0.0.0.0:8088
```

Verify it works:
```bash
curl http://localhost:8088/health
# → {"status":"ok"}
```

## 4. Flash the Display

Plug in your reTerminal via USB-C.

```bash
# For E1001 (monochrome):
pio run -e reterminal_e1001 -t upload --upload-port /dev/ttyUSB0

# For E1002 (color):
pio run -e seeed_xiao_esp32s3 -t upload --upload-port /dev/ttyUSB0
```

If you get "Permission denied":
```bash
sudo chmod 666 /dev/ttyUSB0
```

The display will boot, show a splash screen, connect to WiFi, fetch the first dashboard page, then go to sleep. Press any button to wake it and change pages.

## 5. Trigger a Refresh

```bash
# Push a new dashboard to the display wirelessly
curl http://localhost:8088/trigger          # E1002 (color)
curl http://localhost:8088/trigger-e1001    # E1001 (monochrome)
```

The display wakes within 60 seconds, fetches the page, and refreshes.

## 6. Make It Your Own

### Change what's displayed
Edit `server/server.py` → `get_mock_context()` — this function provides all the data for each page. Replace the demo headlines, agenda items, and stats with your own.

### Change how it looks
Edit the HTML templates in `server/templates/`:
- `newspaper.html` — The Daily Glitch (page 1)
- `weather.html` — Weather dashboard (page 2)
- `maintenance.html` — Maintenance tracker (page 3)

Templates use Jinja2. All data comes from the context dict in `get_mock_context()`.

After editing, restart the server and trigger a refresh:
```bash
pm2 restart epaper-server      # if using PM2
# or Ctrl-C and re-run python3 server.py

curl http://localhost:8088/trigger
```

### Add a new page
1. Create `server/templates/calendar.html`
2. Add context data in `server/server.py` `get_mock_context()` for `calendar.html`
3. Add `"calendar"` to `TEMPLATE_NAMES[]` in `firmware/src/main.cpp`
4. Update `NUM_PAGES` in `main.cpp`
5. Rebuild and flash

### Preview without a display
```bash
# Color preview (what the display will show after dithering)
curl -o preview.png http://localhost:8088/dashboard.png?template=newspaper

# BW preview (for E1001)
curl -o preview.png http://localhost:8088/dashboard-bw.png?template=newspaper

# Full-color preview (before dithering — for design iteration)
curl -o preview.png http://localhost:8088/preview.png?template=newspaper
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Display won't wake | Check power switch on back |
| BLE trigger not working | Wait for next 60s timer wake, or press a button |
| Server 404 on /dashboard-bw.bin | Restart server after code changes |
| Flash fails with "Permission denied" | `sudo chmod 666 /dev/ttyUSB0` |
| Garbled display | Wrong format — BW display getting color data or vice versa |
| Buttons don't respond | Press and hold for 1 second, then release |

## Project Structure

```
reterminal/
├── QUICKSTART.md              # This file — start here
├── README.md                  # Full reference (all endpoints, power profile, etc.)
├── HARDWARE.md                # Complete IO pin map, BMS, charger, sensors
├── AI-MAP.md                  # Agent reference (routing rules, gotchas, data flows)
├── requirements.txt           # Python dependencies
├── server/                    # Flask dashboard renderer
│   ├── server.py              # Routes, mock data, trigger endpoints
│   ├── renderer.py            # HTML→PNG→dither→pack pipeline
│   ├── weather_provider.py    # Live weather (NWS API, no key needed)
│   ├── ble_trigger.py         # BLE push for wireless refresh
│   └── templates/             # Jinja2 HTML templates (800×480)
└── firmware/                  # ESP32-S3 code (PlatformIO + Arduino)
    ├── src/main.cpp           # Shared firmware (E1001 + E1002)
    ├── src/wifi_config.h.example  # WiFi template
    └── platformio.ini         # Two build environments
```

## For AI Agents

If you're an AI agent picking up this project:

1. **Read `AI-MAP.md` first** — it has routing rules, gotchas, and architecture details
2. **Read `HARDWARE.md`** for pin maps and peripheral info
3. **Follow the steps above** in order — they're designed to be mechanically executable
4. **Every change to hardware knowledge goes in `HARDWARE.md`** — keep it current
5. **The `#ifdef` system** in `main.cpp` supports both displays from one file
   - Build flag `-D E1001_VARIANT` → monochrome (env: `reterminal_e1001`)
   - Build flag `-D E1002_VARIANT` → color (env: `seeed_xiao_esp32s3`)
6. **Key gotcha:** Call `display.init(0)` after every deep sleep wake (done in `showPage()`)
7. **BLE is best-effort** — the 60s timer wake is the reliable trigger fallback
