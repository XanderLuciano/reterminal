# HOA Meeting Sign — Reuse Workflow

E-ink notice board sign for Park Springs HOA board meetings (E1002 color Spectra 6,
800×480). Shows date/time, Meeting ID + passcode, and a scannable QR code for the
Zoom link. Solid colors only (no dithering) so the QR stays razor sharp.

## Files

| File | Role |
|---|---|
| `server/gen_hoa.py` | Generator (template + QR + `.bin`). The durable "template" lives here. |
| `server/hoa_meeting.json` | Meeting details (gitignored — holds real passcode/URL). |
| `server/hoa_meeting.example.json` | Placeholder template for the config. |
| `server/templates/hoa-meeting.html` | Generated HTML (gitignored — regenerated). |
| `server/hoa-meeting.bin` | Generated nibble-packed framebuffer (gitignored). |
| `server/hoa_preview.png` | Preview image (gitignored via `server/*.png`). |
| `server/renderer.py` → `render_dashboard_raw_solid()` | No-dither color render path. |
| `server/server.py` → `/hoa.bin` | Serves the sign (solid, 7-day refresh interval). |

## Regenerate for a new meeting

1. **Edit `server/hoa_meeting.json`** — new date, time, meeting ID, passcode, zoom URL.
2. **Generate:** `cd server && python3 gen_hoa.py`
3. **Serve:** `pm2 restart epaper-server` (so `/hoa.bin` picks up the new template).
4. **Push to device:** power-cycle the display or press a button — it refetches
   `/hoa.bin` and shows the new sign. **No reflash needed** once the firmware is
   pointed at `/hoa.bin`.

## First-time device setup (already done Sep 2026)

- Firmware flashed for E1002 (`seeed_xiao_esp32s3`) with:
  - `firmware/src/wifi_config.h`: home WiFi creds (gitignored)
  - `firmware/src/main.cpp` `DASHBOARD_BASE_URL`: `http://<server-ip>:8088/hoa.bin`
- The `/hoa.bin` route sets `X-WiFi-Refresh-Interval: 168` (7 days) so the sign
  won't wake in the box, fail a WiFi check, and overwrite itself with an error screen.

## Meeting cadence

3rd Wednesday monthly, ~7:00 PM (regular session, following Executive Session).
Meeting ID + passcode come from the monthly agenda email (management company `mylordon.com`).
