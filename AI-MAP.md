# AI-MAP.md — EPaper Display Project

> **For AI agents working in this codebase.**  
> Human-readable documentation: `README.md`  
> This file: routing, structure, gotchas, and agent-specific operational knowledge.

---

## Project Directory

```
dev/projects/epaper-display/
├── firmware/                  # ESP32-S3 PlatformIO project (Arduino + GxEPD2)
│   ├── platformio.ini         # Board: seeed_xiao_esp32s3, PSRAM: opi
│   ├── src/main.cpp           # Main firmware (current: v5 select+confirm)
│   └── .pio/libdeps/.../GxEPD2/  # PATCHED library (see GxEPD2 Patches)
├── server/                    # NUC Flask server (renders dashboards)
│   ├── server.py              # Flask app — mock data, routes
│   ├── renderer.py            # HTML→PNG→dither→nibble pack pipeline
│   ├── ble_trigger.py         # BLE client for ESP32 push triggers
│   └── templates/             # Jinja2 HTML templates at 800×480
│       ├── newspaper.html     # Page 1: The Daily Glitch
│       ├── weather.html        # Page 2: Full-color weather
│       └── dashboard.html     # Card-style (legacy)
├── e1002-hello.yaml           # ESPHome attempt (compiles, display untested)
├── pio-test/                  # Original hello-world (legacy)
├── README.md                  # Full human documentation
└── AI-MAP.md                  # This file
```

---

## Routing Rules

### Where to make changes

| What you want to change | Where to go |
|-------------------------|-------------|
| Display content, layout, design | `server/templates/*.html` |
| Mock data, news headlines, weather values | `server/server.py` → `get_mock_context()` / `get_weather_context()` |
| Dithering algorithm, color mapping | `server/renderer.py` → `_SPECTRA6_RGB_TO_NIBBLE`, `dither_spectra6()` |
| Button behavior, sleep timing, BLE params | `firmware/src/main.cpp` |
| Board config, library deps, build flags | `firmware/platformio.ini` |
| GxEPD2 display driver behavior | `firmware/.pio/libdeps/.../GxEPD2/src/GxEPD2_7C.h` (patched) |
| BLE trigger from NUC | `server/ble_trigger.py` |
| Server routes, API | `server/server.py` |

### Do NOT modify

- `firmware/.pio/` — PlatformIO build cache, auto-regenerated
- `server/__pycache__/` — Python cache
- `pio-test/` — legacy, use `firmware/` instead

---

## GxEPD2 Patches

The GxEPD2 library at `firmware/.pio/libdeps/seeed_xiao_esp32s3/GxEPD2/` has TWO patches:

### 1. PSRAM Framebuffer (line ~545)
`_pixel_buffer` changed from fixed array to `uint8_t*` pointer, allocated via `ps_calloc()`.  
**Why:** Frees 192KB from SRAM → makes room for NimBLE.  
**If library is re-extracted:** Must re-apply this patch or NimBLE won't fit.

### 2. loadImageBuffer() method
Added public method to GxEPD2_7C class:
```cpp
void loadImageBuffer(const uint8_t* data, size_t size) {
    memcpy(_pixel_buffer, data, size);
}
```
**Why:** `drawImage()` expects 2-bits-per-pixel format but our renderer produces 4-bits-per-pixel nibble-packed data. Bypassing `drawImage` and copying directly into `_pixel_buffer` then using the paging pipeline is the correct approach.  
**If not present:** Display will show garbled/ghosted content.

---

## Critical Gotchas

### F1: Format Mismatch (drawImage vs nibble-packed)
- **GxEPD2 `drawImage(bitmap, ...)`** → `writeImage` → expects 2 bits/pixel, 100 bytes/row
- **Our nibble-packed data** → 4 bits/pixel, 400 bytes/row
- **Fix:** Use `loadImageBuffer()` + paging, NOT `drawImage` or raw `drawNative`
- **Symptom if broken:** Horizontal banding, ghosted text, unreadable display

### F2: Deep Sleep Wake Polarity
- Buttons use INPUT_PULLUP → normally HIGH → pressed = LOW
- Must use `ESP_EXT1_WAKEUP_ANY_LOW` in `esp_sleep_enable_ext1_wakeup()`
- `ANY_HIGH` causes continuous false wakes (buttons are always HIGH)

### F3: PSRAM Lost After Deep Sleep
- Deep sleep powers down PSRAM. All heap allocations (`ps_malloc`) are gone.
- Framebuffer pointers become dangling. Must `ps_malloc` fresh after each deep sleep wake.
- Light sleep preserves PSRAM but not used in current firmware.

### F4: ESP32-S3 Serial
- `Serial` = USB Serial/JTAG (GPIO19/20) — NOT connected on E1002
- `Serial0` = UART0 (GPIO43 TX, GPIO44 RX) — connected to CH341 USB-serial
- Always use `Serial0` for debug output

### F5: Spectra 6 = NO Partial Refresh
- Hardware limitation. Every `refresh()` is a full 25-45 second cycle.
- Do not attempt "fast page flipping" — won't work.
- UX must accommodate this slowness (hence select+confirm model).

### F6: /dev/ttyUSB0 Permissions
- Can revert to 660 after ESP32 reboot. Fix: `sudo chmod 666 /dev/ttyUSB0`
- Xander is in `dialout` group but udev sometimes needs manual intervention.

---

## Flash & Test Commands

```bash
# Build & flash firmware
cd dev/projects/epaper-display/firmware
sudo chmod 666 /dev/ttyUSB0  # if needed
pio run -t upload --upload-port /dev/ttyUSB0

# Restart server after template/code changes
pm2 restart epaper-server

# Trigger wireless refresh (works even with ESP32 in deep sleep)
curl http://localhost:8088/trigger

# Preview what the display will show (before dithering)
curl -o preview.png http://localhost:8088/preview.png?template=newspaper
curl -o preview.png http://localhost:8088/preview.png?template=weather

# Check server logs for ESP32 activity
pm2 logs epaper-server --lines 10 --nostream | grep dashboard.bin
```

---

## Hardware Quick Reference

| Component | Pin | Notes |
|-----------|-----|-------|
| EPD SCK | GPIO7 | HSPI |
| EPD MOSI | GPIO9 | HSPI |
| EPD CS | GPIO10 | |
| EPD DC | GPIO11 | |
| EPD RESET | GPIO12 | |
| EPD BUSY | GPIO13 | |
| BTN_GREEN | GPIO3 | Active-low, INPUT_PULLUP, confirm action |
| BTN_RIGHT | GPIO4 | Active-low, INPUT_PULLUP, next/right |
| BTN_LEFT | GPIO5 | Active-low, INPUT_PULLUP, prev/left |
| BUZZER | GPIO45 | PWM tone() |
| LED | GPIO6 | Inverted (LOW=ON) |
| CH341 UART RX | GPIO44 | Serial0 |
| CH341 UART TX | GPIO43 | Serial0 |

---

## Interaction Model (v5)

```
DEEP SLEEP (display persists on e-ink)
    │
    ├─ Timer (10 min) → BLE advertise 10s → back to sleep
    │                    (unless BLE trigger received)
    │
    ├─ Timer + Health (3 hrs) → WiFi → fetch current page → refresh → sleep
    │
    └─ Button press → WAKE → beep current page
                          ├─ Left/Right → cycle selection → beep new count
                          ├─ Green → confirm → WiFi → fetch → refresh → sleep
                          └─ 30s timeout → sleep (no change)
```

**Beep patterns:** 1 beep = page 0 (newspaper), 2 beeps = page 1 (weather), ascending triple = confirmed

---

## Server Data Flow

```
Jinja2 template (800×480 HTML)
    → Playwright (chromium headless) screenshot
    → PIL resize 800×480
    → Floyd-Steinberg dither to 6-color Spectra 6 palette
    → Nibble pack (2 pixels per byte, 4 bits per pixel)
    → 192,000 byte .bin file
    → ESP32 fetches via HTTP
    → memcpy into GxEPD2_7C _pixel_buffer
    → _convert_to_native() remaps logical→native color indices
    → SPI write to EPD controller
    → Physical refresh (25-45 sec)
```

---

## Configuration Constants (main.cpp)

| Constant | Value | Notes |
|----------|-------|-------|
| WIFI_SSID | "SpaceLaser" | |
| DEEP_SLEEP_SECONDS | 600 | 10 minutes |
| ADVERTISE_TIMEOUT_S | 10 | BLE advertising window |
| HEALTH_INTERVAL_HOURS | 3 | Auto-refresh interval |
| SELECT_TIMEOUT_S | 30 | Button selection mode timeout |
| FB_SIZE | 192000 | Framebuffer size (800×480 nibble-packed) |
| BLE SERVICE_UUID | a1b2c3d4-... | Scan target for ble_trigger.py |
| DASHBOARD_URL | 192.168.86.31:8088 | NUC Flask server |

---

## Tags

#hardware #esp32 #epaper #eink #spectra6 #gxepd2 #platformio #arduino #flask #ble #nimble #dashboard #rendering
