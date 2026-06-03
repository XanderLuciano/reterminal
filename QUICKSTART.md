# Quick Start — Zero to Working Display

Step-by-step from `git clone` to a wireless e-ink dashboard. ~10 minutes.

> **🤖 Copy-paste this into any AI:**
>
> ```
> You're working with github.com/XanderLuciano/reterminal — an open-source ePaper dashboard project.
> 1. Read this QUICKSTART.md and follow the steps in order
> 2. Read AI-MAP.md for architecture, gotchas, and routing rules
> 3. Read HARDWARE.md for the complete pin map
> 4. Two display variants: E1001 (BW, env reterminal_e1001) and E1002 (color, env seeed_xiao_esp32s3)
> 5. My goal is: [describe what you need]
> ```

## Prerequisites

- reTerminal E1001 (monochrome) or E1002 (color)
- USB-C cable for flashing
- A machine to run the server (any OS with Docker, or Python 3.11+)
- Linux/macOS for local firmware builds; or use the web flasher

## 1. Clone & Configure

```bash
git clone https://github.com/XanderLuciano/reterminal.git
cd reterminal
```

### WiFi
```bash
cp firmware/src/wifi_config.h.example firmware/src/wifi_config.h
# Edit wifi_config.h — set your SSID and password
```

### Server IP
Edit `firmware/src/main.cpp` — change both `DASHBOARD_BASE_URL` entries to your server's IP or hostname.

### Weather (optional)
Edit `server/weather_provider.py`:
- `GRID_ID`, `GRID_X`, `GRID_Y` — your NWS grid point
- Lat/lng in the sunrise and Open-Meteo URLs

## 2. Start Server

Choose one:

### 🐳 Docker (easiest)
```bash
docker compose up -d
# → http://localhost:8088
```

No Python, no Playwright, no dependencies to install on the host.

### 📦 Manual
```bash
pip install -r requirements.txt
playwright install chromium

cd server
python3 server.py
# → http://0.0.0.0:8088
```

Verify either way: `curl http://localhost:8088/health` → `{"status":"ok"}`

## 3. Flash Display

Plug in your reTerminal via USB-C. Two options:

### 🌐 Web Flasher (no local PlatformIO needed)

With the server running (Docker or manual), open `http://<server>:8088/flasher` in **Chrome or Edge** (Web Serial required).

1. Select your display type (E1001 / E1002)
2. Enter WiFi SSID/password and network settings
3. Click Build → wait for PlatformIO to compile (inside the container if using Docker)
4. Click Flash — browser connects to your ESP32-S3 via USB, downloads the firmware, and flashes it

No USB passthrough to Docker. No PlatformIO install. The browser handles everything.

### 🔧 Manual (PlatformIO CLI)

```bash
cd firmware

# E1001 (monochrome):
pio run -e reterminal_e1001 -t upload --upload-port /dev/ttyUSB0

# E1002 (color):
pio run -e seeed_xiao_esp32s3 -t upload --upload-port /dev/ttyUSB0
```

Permission denied? `sudo chmod 666 /dev/ttyUSB0`

The display boots, connects to WiFi, fetches page 1, then sleeps. Press any button to wake and switch pages.

## 4. Trigger a Refresh

```bash
curl http://localhost:8088/trigger          # E1002
curl http://localhost:8088/trigger-e1001    # E1001
```

Display wakes within 60 seconds, fetches the page, refreshes.

## 5. Customize

### Change content
Edit `server/server.py` → `get_mock_context()`. Replace demo headlines, agenda, stats. Restart server.

### Change layout
Edit `server/templates/*.html` — Jinja2 at 800×480. Restart server and trigger refresh.

### Add a new page
1. Create `server/templates/my_page.html`
2. Add context in `server/server.py` → `get_mock_context()` for `my_page.html`
3. Add `"my_page"` to `TEMPLATE_NAMES[]` in `firmware/src/main.cpp`
4. Update `NUM_PAGES`
5. Rebuild and flash

### Add a URL page (no HTML needed)
1. Add an entry to `server/url_pages.json` (name, URL, refresh_seconds, enabled:true)
2. Add the page name to `TEMPLATE_NAMES[]` in firmware
3. Update `NUM_PAGES`
4. Rebuild and flash

The server auto-fetches, screenshots, and refreshes on schedule.

### Preview without a display
```bash
curl -o preview.png http://localhost:8088/preview.png?template=newspaper     # full color
curl -o preview.png http://localhost:8088/dashboard-bw.png?template=weather  # BW dithered
```

## For AI Agents

If you're an AI picking up this project:

1. **Read `AI-MAP.md`** — routing rules, architecture, critical gotchas
2. **Read `HARDWARE.md`** — pin maps and peripheral reference
3. **Follow the steps above in order** — they're mechanically executable
4. **Two build targets:** `reterminal_e1001` (BW) and `seeed_xiao_esp32s3` (color)
5. **Key gotchas:**
   - Call `display.init(0)` after every deep sleep wake (handled in `showPage()`)
   - `#ifdef E1001_VARIANT` / `E1002_VARIANT` controls display-specific code
   - BLE is best-effort; 60s timer wake is the reliable fallback
   - WiFi credentials live in `wifi_config.h` (gitignored, copy from `.example`)
6. **Update `HARDWARE.md`** whenever you discover new hardware details
