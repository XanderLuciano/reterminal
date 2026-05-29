# E1001 + E1002 ePaper Dashboards — Wireless

Two wireless e-ink dashboards running the same codebase — the NUC renders pages, pushes updates via BLE, and the displays fetch over WiFi.

## Hardware

| | E1002 | E1001 |
|---|---|---|
| **Display** | 7.3" Spectra 6 color | 7.5" monochrome BW |
| **Resolution** | 800×480 | 800×480 |
| **Colors** | 6 (black, white, yellow, red, blue, green) | 2 (black, white) |
| **Driver** | GxEPD2_730c_GDEP073E01 | GxEPD2_750_GDEY075T7 |
| **Controller** | UC8179 | UC8179 |
| **MCU** | ESP32-S3, 8MB PSRAM | ESP32-S3, 8MB PSRAM |
| **BLE name** | E1002-Dashboard | E1001-Dashboard |

## What's on the Display

3 pages total, shared between both displays:

- **Page 1 — The Daily Glitch** (newspaper layout)
- **Page 2 — Weather** (real NWS API data, no key needed)
- **Page 3 — Maintenance** (home maintenance tracker)

## How to Use the Buttons

Select-then-confirm model (same on both displays):

1. **Press any button** — wakes display, beeps current page (1 beep = newspaper, 2 = weather, 3 = maintenance)
2. **Left or Right** — switch between pages, beeps change with selection
3. **Green button** — confirms → ascending beep → refreshes to selected page → back to sleep
4. Do nothing for 30 seconds → goes back to sleep, no change

*E-ink keeps showing the last image even when "off" with zero power.*

## Triggering a Wireless Refresh

From the NUC (or any device on the network):

```bash
# E1002 (color)
curl http://192.168.86.31:8088/trigger

# E1001 (monochrome)
curl http://192.168.86.31:8088/trigger-e1001
```

This pre-renders a fresh dashboard and sends a BLE wake signal. The ESP32 wakes within 60 seconds, fetches the page over WiFi, refreshes the display, and goes back to sleep.

**BLE trigger latency:** ≤60 seconds (display checks for triggers every 60 seconds with a 10-second BLE advertising window).

## Power Profile

| Mode | Power draw | Duration |
|---|---|---|
| Deep sleep | ~50µA | 60s between checks |
| BLE advertising | ~50mA | 10s window |
| WiFi + display refresh | ~500mA | ~45s burst |
| **Estimated battery life** | **3-4 weeks** | (2000mAh battery) |

WiFi is only used when a BLE trigger is received, a button is pressed, or the 6-hour health refresh fires. No wasted WiFi cycles.

## Server Endpoints

| What it does | URL |
|---|---|
| Trigger E1002 refresh | `GET /trigger` |
| Trigger E1001 refresh | `GET /trigger-e1001` |
| E1002 framebuffer (4-bit nibble) | `GET /dashboard.bin?template=newspaper` |
| E1001 framebuffer (1-bit packed) | `GET /dashboard-bw.bin?template=newspaper` |
| Color-dithered preview (E1002) | `GET /dashboard.png?template=weather` |
| BW-dithered preview (E1001) | `GET /dashboard-bw.png?template=newspaper` |
| Full-color preview (before dither) | `GET /preview.png?template=newspaper` |
| Health check | `GET /health` |

All at `http://192.168.86.31:8088`

## Build & Flash

```bash
cd dev/projects/epaper-display/firmware

# Build & flash E1001 (monochrome)
pio run -e reterminal_e1001 -t upload --upload-port /dev/ttyUSB0

# Build & flash E1002 (color)
pio run -e seeed_xiao_esp32s3 -t upload --upload-port /dev/ttyUSB0
```

If you get "Permission denied" on `/dev/ttyUSB0`:
```bash
sudo chmod 666 /dev/ttyUSB0
```

**WiFi credentials:** Copy `firmware/src/wifi_config.h.example` → `wifi_config.h` and fill in your network. The real file is gitignored.

## Adding a New Page

1. Create a new template in `server/templates/` (e.g., `calendar.html`)
2. Add context data in `server/server.py` `get_mock_context()`
3. Add the URL to `TEMPLATE_NAMES[]` array in `firmware/src/main.cpp`
4. Update `NUM_PAGES` in `main.cpp`
5. Rebuild and flash both displays

## Project Layout

```
epaper-display/
├── firmware/                  # ESP32 code (PlatformIO + Arduino)
│   ├── src/main.cpp           # Shared code, #ifdef per variant
│   ├── src/wifi_config.h.example  # Template, gitignored real file
│   └── platformio.ini         # Two envs: E1001 + E1002
├── server/                    # Flask server on NUC
│   ├── server.py              # Routes, mock data, trigger endpoints
│   ├── renderer.py            # HTML→PNG→dither→pack (color + BW)
│   ├── weather_provider.py    # NWS + Open-Meteo APIs (no keys)
│   ├── ble_trigger.py         # BLE push to ESP32 (multi-device)
│   └── templates/             # Shared page designs (Jinja2 HTML)
├── README.md                  # This file
└── AI-MAP.md                  # Agent reference (debugging, internals)
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Display won't wake | Power switch off on back | Flip the switch |
| BLE trigger not connecting | NUC Bluetooth stack (BlueZ) issue | Wait for next timer wake, or press a button |
| Blank/white screen after refresh | PSRAM framebuffer corrupted | Trigger another refresh, check server logs |
| Garbled/ghosted display | Format mismatch in GxEPD2 | Reflash — BW display getting nibble data or vice versa |
| Buttons not responding | ESP32 in deep sleep | Press and hold for 1 sec, then release |
| Server returns errors | Playwright or Python deps | `pm2 logs epaper-server` to check |

## Things to Know

- **E1002 refresh is SLOW.** 25-45 seconds is normal for Spectra 6 color e-ink. E1001 (BW) is faster at ~5 seconds.
- **No partial refresh on color.** E1002 always does full refresh. E1001 could theoretically do partial but doesn't currently.
- **Image persists without power.** E-ink keeps showing whatever was last displayed even with zero power.
- **Auto-refresh every 6 hours** prevents ghosting from static images.
- **Separate BLE UUIDs.** Each device has its own service/characteristic UUIDs — triggers never cross-fire.
