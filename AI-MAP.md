# AI-MAP.md — EPaper Display Project

> **For AI agents working in this codebase.**  
> Human-readable documentation: `README.md`  
> This file: routing, structure, gotchas, and agent-specific operational knowledge.

---

## Project Directory

```
dev/projects/epaper-display/
├── firmware/                  # ESP32-S3 PlatformIO (Arduino + GxEPD2)
│   ├── platformio.ini         # Two envs: seeed_xiao_esp32s3 (E1002), reterminal_e1001 (E1001)
│   ├── src/main.cpp           # Shared firmware, #ifdef E1001_VARIANT / E1002_VARIANT
│   ├── src/wifi_config.h      # REAL creds (gitignored) — copy from .example
│   ├── src/wifi_config.h.example  # Template with placeholders
│   └── .pio/libdeps/.../GxEPD2/  # PATCHED library (see GxEPD2 Patches)
├── server/                    # NUC Flask server (renders dashboards)
│   ├── server.py              # Flask app — mock data, routes, trigger endpoints
│   ├── renderer.py            # HTML→PNG→dither→pack (Spectra 6 + BW pipelines)
│   ├── weather_provider.py    # NWS + Open-Meteo APIs (free, no keys)
│   ├── ble_trigger.py         # BLE client — per-device UUID config, multi-target
│   └── templates/             # Jinja2 HTML templates at 800×480 (shared)
│       ├── newspaper.html     # Page 1: The Daily Glitch
│       ├── weather.html       # Page 2: Weather dashboard
│       ├── maintenance.html   # Page 3: Home maintenance tracker
│       └── dashboard.html     # Card-style (legacy)
├── e1002-hello.yaml           # ESPHome attempt (compiles, display untested)
├── pio-test/                  # Original hello-world (legacy, gitignored)
├── README.md                  # Full human documentation
├── HARDWARE.md                # Complete IO pin reference
└── AI-MAP.md                  # This file
```

---

## Two Variants, One Codebase

| | E1002 (color) | E1001 (monochrome) |
|---|---|---|
| **Build env** | `seeed_xiao_esp32s3` | `reterminal_e1001` |
| **Build flag** | `-D E1002_VARIANT` | `-D E1001_VARIANT` |
| **GxEPD2 class** | `GxEPD2_7C` | `GxEPD2_BW` |
| **Display driver** | `GxEPD2_730c_GDEP073E01` | `GxEPD2_750_GDEY075T7` |
| **Panel** | 7.3" Spectra 6 | 7.5" B&W |
| **FB_SIZE** | `(800*480+1)/2` = 192,000B | `(800*480+7)/8` = 48,000B |
| **Server endpoint** | `/dashboard.bin` | `/dashboard-bw.bin` |
| **BLE name** | E1002-Dashboard | E1001-Dashboard |
| **BLE service UUID** | a1b2c3d4-... | c3d4e5f6-... |
| **BLE trigger UUID** | b2c3d4e5-... | d4e5f6a7-... |

Pinout is identical for both devices. Same ESP32-S3 chip.

---

## Routing Rules

### Where to make changes

| What you want to change | Where to go |
|---|---|
| Display content, layout, design | `server/templates/*.html` (shared between both displays) |
| Pin mappings, IO, BMS, charger, sensor details | `HARDWARE.md` — **always update this** when you discover or change hardware info |
| Mock data, news headlines, reminders | `server/server.py` → `get_mock_context()` |
| Weather data | `server/weather_provider.py` |
| Color dithering (E1002) | `server/renderer.py` → `dither_spectra6()`, `pack_nibbles()` |
| BW dithering (E1001) | `server/renderer.py` → `dither_bw()`, `pack_bits()` |
| Button behavior, sleep timing, BLE | `firmware/src/main.cpp` (shared, #ifdef per variant) |
| Board config, build flags | `firmware/platformio.ini` |
| BLE trigger from NUC | `server/ble_trigger.py` → `DEVICE_CONFIG` dict |
| Server routes | `server/server.py` |
| WiFi credentials | `firmware/src/wifi_config.h` (local only, gitignored) |

### Do NOT modify

- `firmware/.pio/` — PlatformIO build cache
- `server/__pycache__/` — Python cache
- `pio-test/` — legacy
- `firmware/src/wifi_config.h` — local secrets file

### MUST maintain

- **`HARDWARE.md`** — the canonical hardware IO reference. Any time you discover a new pin, peripheral, register, sensor address, or power detail, update this file. It's the source of truth for all hardware knowledge discovered about these devices. Do NOT let it go stale.

---

## GxEPD2 Patches

The GxEPD2 library at `firmware/.pio/libdeps/seeed_xiao_esp32s3/GxEPD2/` (E1002) has patches:

### 1. PSRAM Framebuffer (line ~545)
`_pixel_buffer` changed from fixed array to `uint8_t*` pointer, allocated via `ps_calloc()`.  
**Why:** Frees 192KB from SRAM → makes room for NimBLE.  
**If library is re-extracted:** Must re-apply this patch or NimBLE won't fit.

### 2. loadImageBuffer() method (E1002 only)
Added public method to GxEPD2_7C class:
```cpp
void loadImageBuffer(const uint8_t* data, size_t size) {
    memcpy(_pixel_buffer, data, size);
}
```
**Why:** `drawImage()` expects 2-bits-per-pixel but our renderer produces 4-bit nibble-packed data. Direct memcpy bypasses the format mismatch.  
**If not present:** Display shows garbled/ghosted content.

### E1001 note
E1001 uses `drawBitmap()` which expects 1-bit packed data — no patch needed. `drawBitmap(0, 0, framebuf, 800, 480, GxEPD_BLACK)` works natively.

---

## Critical Gotchas

### F1: Format Mismatch Per Display
- **E1002:** 4-bit nibble-packed (2px/byte). Uses `loadImageBuffer()` + paging. Do NOT use `drawImage`.
- **E1001:** 1-bit packed (8px/byte, MSB first). Uses `drawBitmap()`. Do NOT use nibble data.
- **Wrong format → garbled display.**

### F2: Deep Sleep Wake Polarity
- Buttons: INPUT_PULLUP → normally HIGH → pressed = LOW
- Must use `ESP_EXT1_WAKEUP_ANY_LOW`
- `ANY_HIGH` causes continuous false wakes

### F3: PSRAM Lost After Deep Sleep
- Deep sleep powers down PSRAM. All `ps_malloc` allocations gone.
- Must `ps_malloc` fresh after each deep sleep wake.
- Light sleep preserves PSRAM but not used.

### F4: ESP32-S3 Serial
- `Serial` = USB Serial/JTAG (GPIO19/20) — NOT connected
- `Serial0` = UART0 (GPIO43 TX, GPIO44 RX) — connected to CH341 USB-serial
- Always use `Serial0` for debug output

### F5: Spectra 6 = NO Partial Refresh (E1002 only)
- Hardware limitation. Every refresh is 25-45 sec full cycle.
- E1001 (BW) is faster (~5 sec) and could theoretically partial-refresh.

### F6: /dev/ttyUSB0 Permissions
- Can revert to 660 after ESP32 reboot. Fix: `sudo chmod 666 /dev/ttyUSB0`

### F8: Display Must Re-init After Deep Sleep
- EPD controller (UC8179) loses power state during deep sleep
- Must call `display.init(0)` on EVERY wake, not just first boot
- Without it: display appears frozen, won't change pages
- Fixed in showPage() which calls init() before any display operation

### F7: BlueZ BLE Connection Issues
- NUC's BlueZ stack sometimes fails with `br-connection-canceled` or `UNLIKELY_ERROR`
- Workaround: display wakes on timer every 60s anyway — web trigger pre-renders, next wake picks it up
- BLE is best-effort; the 60s timer wake is the reliable fallback

---

## Flash & Test Commands

```bash
# E1001 (monochrome)
cd dev/projects/epaper-display/firmware
sudo chmod 666 /dev/ttyUSB0
pio run -e reterminal_e1001 -t upload --upload-port /dev/ttyUSB0

# E1002 (color)
pio run -e seeed_xiao_esp32s3 -t upload --upload-port /dev/ttyUSB0

# Build both without flashing
pio run -e reterminal_e1001 -e seeed_xiao_esp32s3

# Restart server after template/code changes
pm2 restart epaper-server

# Trigger wireless refresh
curl http://localhost:8088/trigger          # E1002
curl http://localhost:8088/trigger-e1001    # E1001

# Preview what the display will show (before dithering)
curl -o preview.png http://localhost:8088/preview.png?template=newspaper
curl -o bw_preview.png http://localhost:8088/dashboard-bw.png?template=newspaper

# Test raw framebuffer
curl -o test.bin http://localhost:8088/dashboard-bw.bin?template=newspaper
# E1001: 48,000 bytes (800×480/8)
# E1002: 192,000 bytes (800×480/2)

# Check server logs
pm2 logs epaper-server --lines 10 --nostream
```

---

## Hardware Quick Reference

**Full reference:** `HARDWARE.md` — complete pin map, BMS, charger I2C, power architecture.

| Component | Pin | Notes |
|---|---|---|
| EPD SCK | GPIO7 | HSPI |
| EPD MOSI | GPIO9 | HSPI |
| EPD CS | GPIO10 | |
| EPD DC | GPIO11 | |
| EPD RESET | GPIO12 | |
| EPD BUSY | GPIO13 | |
| BTN_GREEN | GPIO3 | Active-low, INPUT_PULLUP, confirm |
| BTN_RIGHT | GPIO4 | Active-low, INPUT_PULLUP, next |
| BTN_LEFT | GPIO5 | Active-low, INPUT_PULLUP, prev |
| LED | GPIO6 | Active-low (LOW=ON), charging indicator |
| BUZZER | GPIO45 | PWM tone() |
| BATT_ENABLE | GPIO21 | Enable battery ADC divider |
| BATT_ADC | GPIO1 | Analog battery voltage (÷2 divider) |
| CHARGER_SDA | GPIO39 | SY6974B I2C1 @ 0x6B |
| CHARGER_SCL | GPIO40 | SY6974B I2C1 @ 0x6B |
| I2C0_SDA | GPIO19 | SHT40 (0x44) + PCF8563 RTC (0x51) |
| I2C0_SCL | GPIO20 | |
| CH341 UART RX | GPIO44 | Serial0 debug console |
| CH341 UART TX | GPIO43 | Serial0 debug console |

Same pinout for both E1001 and E1002.

---

## Interaction Model (v6)

```
DEEP SLEEP (display persists on e-ink)
    │
    ├─ Timer (60s) → BLE advertise 10s → check for trigger
    │                 ├─ Trigger received → WiFi → fetch → refresh → sleep
    │                 └─ No trigger → back to sleep
    │
    ├─ Timer + Health (6h) → WiFi → fetch current page → refresh → sleep
    │
    └─ Button press → WAKE → beep current page
                       ├─ Left/Right → cycle selection → beep new count
                       ├─ Green → confirm → WiFi → fetch → refresh → sleep
                       └─ 30s timeout → sleep (no change)
```

**Beep patterns:** 1 beep = page 0, 2 = page 1, 3 = page 2, ascending triple = confirmed

---

## Server Data Flow

### E1002 (color)
```
Jinja2 template (800×480 HTML)
    → Playwright (chromium headless) screenshot
    → PIL resize 800×480
    → Floyd-Steinberg dither to 6-color Spectra 6 palette
    → Nibble pack (2px/byte, 4 bits/px)
    → 192,000 byte .bin
    → ESP32 HTTP GET /dashboard.bin
    → memcpy → GxEPD2_7C _pixel_buffer
    → SPI write to EPD controller
    → Physical refresh (25-45 sec)
```

### E1001 (monochrome)
```
Jinja2 template (800×480 HTML)
    → Playwright (chromium headless) screenshot
    → PIL convert grayscale → resize 800×480
    → Floyd-Steinberg dither to 1-bit B&W
    → Bit pack (8px/byte, MSB first)
    → 48,000 byte .bin
    → ESP32 HTTP GET /dashboard-bw.bin
    → drawBitmap(0, 0, framebuf, 800, 480, GxEPD_BLACK)
    → SPI write to EPD controller
    → Physical refresh (~5 sec)
```

---

## Power Configuration (shared, main.cpp)

| Constant | Value | Notes |
|---|---|---|
| DEEP_SLEEP_SECONDS | 60 | BLE check every 60 seconds |
| ADVERTISE_TIMEOUT_S | 10 | BLE advertising window |
| HEALTH_INTERVAL_HOURS | 6 | Auto WiFi refresh (ghosting prevention) |
| SELECT_TIMEOUT_S | 30 | Button selection mode timeout |
| Estimated battery life | 3-4 weeks | 2000mAh battery |

---

## ble_trigger.py — Per-Device Config

```python
DEVICE_CONFIG = {
    "E1002-Dashboard": {
        "service": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "trigger": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    },
    "E1001-Dashboard": {
        "service": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "trigger": "d4e5f6a7-b8c9-0123-defa-234567890123",
    },
}
```

Pass `--name "E1001-Dashboard"` to target the mono display. UUIDs auto-resolved from DEVICE_CONFIG.

---

## Tags

#hardware #esp32 #epaper #eink #spectra6 #gxepd2 #platformio #arduino #flask #ble #nimble #dashboard #rendering #monochrome
