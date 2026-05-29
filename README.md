# E1001 + E1002 ePaper Dashboards — Wireless

> **🚀 Just got here?** [`QUICKSTART.md`](QUICKSTART.md) — zero to working display in ~10 minutes.

> **🤖 Point your AI here** — copy-paste this into Claude, ChatGPT, or any AI assistant:
>
> ```
> You're working with the reTerminal ePaper Dashboard project from github.com/XanderLuciano/reterminal.
>
> 1. Read QUICKSTART.md — it has step-by-step setup instructions
> 2. Read AI-MAP.md — routing rules, gotchas, and architecture
> 3. Read HARDWARE.md — complete pin map and peripheral reference
> 4. The project supports two displays: E1001 (monochrome, env reterminal_e1001) and E1002 (color, env seeed_xiao_esp32s3)
> 5. Follow the steps in order — they're designed to be mechanically executable
>
> My goal is: [describe what you need — set up a display, create a custom page, add a data source, etc.]
> ```

Two wireless e-ink dashboards sharing one codebase. The server renders pages, pushes updates via BLE, and the displays fetch them over WiFi.

## Hardware

| | E1002 | E1001 |
|---|---|---|
| **Display** | 7.3" Spectra 6 color | 7.5" monochrome BW |
| **Resolution** | 800×480 | 800×480 |
| **Colors** | 6 (black, white, yellow, red, blue, green) | 2 (black, white) |
| **Refresh time** | 25-45 sec | ~5 sec |
| **MCU** | ESP32-S3, 8MB PSRAM | ESP32-S3, 8MB PSRAM |
| **BLE name** | E1002-Dashboard | E1001-Dashboard |

## Pages

3 pages on both displays:

- **Page 1 — The Daily Glitch** — newspaper layout with headlines, weather snapshot, agenda
- **Page 2 — Weather** — full dashboard with live NWS data (no API key needed)
- **Page 3 — Maintenance** — home maintenance tracker with overdue/status indicators

## Buttons

Select-then-confirm model. Press any button to wake → Left/Right to switch pages → Green to confirm. 30-second timeout returns to sleep. Beeps indicate current page (1 beep = page 1, 2 = page 2, 3 = page 3). E-ink keeps showing the last image with zero power.

## Wireless Refresh

```bash
curl http://YOUR_SERVER_IP:8088/trigger          # E1002 (color)
curl http://YOUR_SERVER_IP:8088/trigger-e1001    # E1001 (mono)
```

Pre-renders the dashboard and sends a BLE wake signal. Display wakes within 60 seconds, fetches over WiFi, refreshes, returns to sleep. BLE is best-effort — the 60-second timer wake is the reliable fallback.

## Power

| Mode | Draw | Duration |
|---|---|---|
| Deep sleep | ~50µA | 60s between checks |
| BLE advertising | ~50mA | 10s window |
| WiFi + refresh | ~500mA | ~45s burst |
| **Battery life** | **3-4 weeks** | 2000mAh |

WiFi only fires on BLE trigger, button press, or 6-hour health refresh.

## Server Endpoints

| Endpoint | Description |
|---|---|
| `GET /trigger` | Trigger E1002 refresh |
| `GET /trigger-e1001` | Trigger E1001 refresh |
| `GET /dashboard.bin?template=name` | E1002 framebuffer (192KB nibble-packed) |
| `GET /dashboard-bw.bin?template=name` | E1001 framebuffer (48KB bit-packed) |
| `GET /dashboard.png?template=name` | Color-dithered preview |
| `GET /dashboard-bw.png?template=name` | BW-dithered preview |
| `GET /preview.png?template=name` | Full-color preview (before dithering) |
| `GET /health` | Health check |

Templates: `newspaper`, `weather`, `maintenance`.

URL-based pages also supported — see [`url_pages.json`](server/url_pages.json).

## Quick Setup

See [`QUICKSTART.md`](QUICKSTART.md) for the full walkthrough. TL;DR:

```bash
git clone https://github.com/XanderLuciano/reterminal.git
cd reterminal
pip install -r requirements.txt && playwright install chromium
cp firmware/src/wifi_config.h.example firmware/src/wifi_config.h  # edit with your WiFi
# Edit firmware/src/main.cpp — change DASHBOARD_BASE_URL to your server's IP
cd server && python3 server.py &
cd ../firmware
pio run -e reterminal_e1001 -t upload --upload-port /dev/ttyUSB0   # E1001
# or: pio run -e seeed_xiao_esp32s3 -t upload --upload-port /dev/ttyUSB0  # E1002
```

## Making It Your Own

### URL Pages — point at any website

Drop URLs into `server/url_pages.json` and they become pages on your display. The server screenshots them at 800×480, dithers for e-ink, and auto-refreshes on schedule.



Add `"my_dashboard"` to `TEMPLATE_NAMES[]` in firmware, rebuild, flash. Endpoints:
- `GET /page/my_dashboard.bin` — BW framebuffer (E1001)
- `GET /page/my_dashboard_color.bin` — color framebuffer (E1002)

### Edit HTML templates

- **Content:** Edit `server/server.py` → `get_mock_context()` — headlines, agenda, stats
- **Weather location:** Update coordinates in `server/weather_provider.py`
- **Layout:** Edit HTML templates in `server/templates/` — Jinja2, 800×480
- **Newspaper name:** Change the masthead in `server/templates/newspaper.html`
- **New page:** Create template → add context → add to `TEMPLATE_NAMES[]` in firmware → rebuild & flash

Restart the server and trigger a refresh to see changes. Full details in [`QUICKSTART.md`](QUICKSTART.md).

## Project Layout

```
├── QUICKSTART.md              # Step-by-step setup (start here!)
├── README.md                  # This file — overview & reference
├── HARDWARE.md                # Complete IO pin map & peripherals
├── AI-MAP.md                  # Agent reference (routing, gotchas, data flows)
├── requirements.txt           # Python dependencies
├── server/                    # Flask dashboard renderer
│   ├── server.py              # Routes, mock data
│   ├── renderer.py            # HTML→PNG→dither→pack (color + BW)
│   ├── weather_provider.py    # Live weather (free NWS API)
│   ├── ble_trigger.py         # BLE push trigger
│   └── templates/             # Jinja2 HTML (800×480)
└── firmware/                  # ESP32-S3 (PlatformIO + Arduino)
    ├── src/main.cpp           # Shared code, #ifdef per variant
    ├── src/wifi_config.h.example
    └── platformio.ini         # Two envs: reterminal_e1001, seeed_xiao_esp32s3
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Display won't wake | Check power switch on back |
| BLE trigger not working | Wait for next 60s timer wake, or press a button |
| Garbled display | BW display getting color data or vice versa — check build target |
| Buttons don't respond | Press and hold for 1 second, then release |
| Server errors | `pm2 logs epaper-server` or check terminal output |

## Key Facts

- Separate BLE UUIDs per device — triggers never cross-fire
- Image persists with zero power (e-ink)
- Auto-refresh every 6 hours prevents ghosting
- E1002 color refresh is SLOW (25-45s), E1001 BW is fast (~5s)
- Default mock data is generic and demo-friendly
