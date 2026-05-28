# E1002 ePaper Display — Wireless Dashboard

A 7.3" full-color e-ink dashboard that sits on my desk and shows The Daily Glitch (newspaper) and a weather page. Updates wirelessly — the NUC pushes updates via BLE, or I can wake it with the buttons.

**Hardware:** Seeed Studio reTerminal E1002 (ESP32-S3, 8MB PSRAM, 2000mAh battery)

## What's on the Display

**Page 1 — The Daily Glitch** (newspaper layout)
- Lead story, second story, weather snapshot, agenda, stats
- Looks like a tiny newspaper

**Page 2 — Weather** (full-color dashboard)
- Current temp, humidity, wind, UV index, sunrise/sunset, 5-day forecast
- Uses all 6 Spectra 6 colors (red, yellow, green, blue, black, white)

*Previews of both pages are at `server/templates/` — open the HTML files in a browser to see what they look like.*

## How to Use the Buttons

The display is slow (25-45 sec per refresh), so it uses a select-then-confirm model:

1. **Press any button** — wakes display, beeps current page (1 beep = newspaper, 2 = weather)
2. **Left or Right** — switch between pages, beeps change with selection
3. **Green button** — confirms → ascending beep → refreshes to selected page → goes back to sleep
4. Do nothing for 30 seconds → goes back to sleep, no change

*The display keeps showing its last image even when "off" — that's how e-ink works.*

## Triggering a Wireless Refresh

From the NUC (or any device on the network):

```bash
curl http://192.168.86.31:8088/trigger
```

This renders a fresh dashboard and pushes a BLE wake signal to the display. The ESP32 wakes within 30 seconds, fetches the new page over WiFi, refreshes, and goes back to sleep.

## Changing What's Displayed

### Edit content (headlines, weather data, etc.)
Edit `server/server.py` — the `get_mock_context()` and `get_weather_context()` functions contain all the data. Restart the server after editing.

### Edit layout / design
Edit the HTML templates in `server/templates/` — they're plain Jinja2 HTML rendered at 800×480 via Playwright. Restart the server and trigger a refresh to see changes.

### Restart the server
```bash
pm2 restart epaper-server
```

## Adding a New Page

1. Create a new template in `server/templates/` (e.g., `calendar.html`)
2. Add context data in `server/server.py` `get_mock_context()`
3. Add the URL to `DASHBOARD_URLS[]` array in `firmware/src/main.cpp`
4. Update `NUM_PAGES` in `main.cpp`
5. Rebuild and flash the firmware

## Build & Flash

```bash
cd dev/projects/epaper-display/firmware
pio run -t upload --upload-port /dev/ttyUSB0
```

If you get "Permission denied" on `/dev/ttyUSB0`:
```bash
sudo chmod 666 /dev/ttyUSB0
```

## Server Endpoints

| What it does | URL |
|-------------|-----|
| Trigger a refresh (renders + BLE push) | `GET /trigger` |
| Raw framebuffer data (ESP32 fetches this) | `GET /dashboard.bin?template=newspaper` |
| Dithered preview (what ESP32 will display) | `GET /dashboard.png?template=weather` |
| Full-color preview (before dithering) | `GET /preview.png?template=newspaper` |
| Health check | `GET /health` |

All at `http://192.168.86.31:8088`

## Project Layout

```
epaper-display/
├── firmware/                  # ESP32 code (PlatformIO + Arduino)
│   ├── src/main.cpp           # Button logic, BLE, WiFi, display
│   └── platformio.ini         # Board config
├── server/                    # Flask server on NUC
│   ├── server.py              # Routes, mock data
│   ├── renderer.py            # HTML→PNG→dither→nibble pack
│   ├── ble_trigger.py         # BLE push to ESP32
│   └── templates/             # Page designs (Jinja2 HTML)
├── README.md                  # This file
└── AI-MAP.md                  # Agent reference (debugging, internals)
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Display won't wake | Power switch off on back | Flip the switch |
| Beeping when not touched | False wake from electrical noise | Reflash — early firmware had `ANY_HIGH` bug |
| Blank/white screen after refresh | PSRAM framebuffer corrupted | Trigger another refresh, check server logs |
| Garbled/ghosted display | Format mismatch in GxEPD2 | Reflash — fixed in v2+ firmware |
| Buttons not responding | ESP32 in deep sleep | Press and hold for 1 sec, then release |
| Server returns errors | Playwright or Python deps | `pm2 logs epaper-server` to check |

## Things to Know

- **Refresh is SLOW.** 25-45 seconds is normal for Spectra 6 color e-ink. Black-and-white e-ink is faster, but we wanted color.
- **No partial refresh.** Color e-ink doesn't support it. Every page change is a full refresh cycle.
- **Battery lasts weeks.** The ESP32 deep-sleeps most of the time. Buttons and the 10-minute BLE check are the only wake sources.
- **Image persists without power.** E-ink keeps showing whatever was last displayed even with zero power.
- **Auto-refresh every 3 hours** prevents ghosting from static images.

## Next Up

- [ ] Real weather API instead of mock data
- [ ] Calendar page with upcoming events
- [ ] Use onboard temperature/humidity sensor
- [ ] Battery level monitoring
