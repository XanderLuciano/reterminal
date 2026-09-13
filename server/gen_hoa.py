#!/usr/bin/env python3
"""
HOA meeting e-ink sign generator — E1002 color, SOLID colors, no dithering.

REUSE (next meeting):
  1. Edit hoa_meeting.json (date, time, meeting id, passcode, zoom URL).
  2. Run:  python3 gen_hoa.py
  3. Outputs: templates/hoa-meeting.html, hoa_preview.png, hoa-meeting.bin
  4. Restart the Flask server (pm2 restart epaper-server) so /hoa.bin serves
     the updated sign, then power-cycle / button-press the device to refetch.
     No reflash needed.

Full workflow: see HOA-SIGN.md
"""
import base64
import io
import json
from pathlib import Path
import qrcode
from PIL import Image
from renderer import render_html, pack_nibbles, SPECTRA6_PALETTE

HERE = Path(__file__).parent
TEMPLATES = HERE / "templates"

# Spectra 6 solid colors we use (exact palette hex)
C_BLUE = "#0000FF"
C_RED = "#FF0000"
C_BLACK = "#000000"
C_WHITE = "#FFFFFF"


def load_meeting() -> dict:
    cfg = HERE / "hoa_meeting.json"
    if not cfg.exists():
        raise SystemExit(
            f"Missing {cfg}. Copy hoa_meeting.example.json -> hoa_meeting.json "
            "and fill in the meeting details."
        )
    return json.loads(cfg.read_text())


def qr_data_uri(url: str, box_size: int = 8, border: int = 2) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    m = load_meeting()
    qr_uri = qr_data_uri(m["zoom_url"])

    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 800px; height: 480px;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    background: {C_WHITE}; color: {C_BLACK};
    overflow: hidden;
    display: grid; grid-template-columns: 1fr 360px;
  }}
  .info {{ padding: 0; display: flex; flex-direction: column; }}
  .header {{
    background: {C_BLUE}; color: {C_WHITE};
    padding: 18px 28px; font-size: 26px; font-weight: 800; letter-spacing: 4px;
  }}
  .body {{ padding: 26px 28px 22px; display: flex; flex-direction: column; gap: 16px; }}
  .title {{ font-size: 46px; font-weight: 800; line-height: 1.0; }}
  .weekday {{ font-size: 24px; font-weight: 800; }}
  .date {{ font-size: 24px; font-weight: 800; }}
  .time {{ font-size: 30px; font-weight: 800; margin-top: 6px; }}
  .fields {{ display: flex; flex-direction: column; gap: 10px; }}
  .field {{
    font-size: 21px; font-weight: 700;
    background: {C_WHITE}; border: 3px solid {C_BLACK}; border-radius: 10px;
    padding: 11px 16px;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .field .lbl {{ font-weight: 400; font-size: 15px; }}
  .field .val {{ letter-spacing: 1px; }}
  .zoom {{ font-size: 15px; font-weight: 600; word-break: break-all; }}
  .qr {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 10px; padding: 20px 24px;
    border-left: 3px solid {C_BLACK};
  }}
  .qr img {{ width: 300px; height: 300px; image-rendering: pixelated; }}
  .qr .cap {{ font-size: 26px; font-weight: 800; color: {C_RED}; }}
</style>
</head>
<body>
  <div class="info">
    <div class="header">{m['org']}</div>
    <div class="body">
      <div class="title">{m['title']}</div>
      <div>
        <div class="weekday">{m['weekday']}</div>
        <div class="date">{m['date']}</div>
        <div class="time">{m['time']} · {m['location']}</div>
      </div>
      <div class="fields">
        <div class="field"><span class="lbl">Meeting ID</span><span class="val">{m['meeting_id']}</span></div>
        <div class="field"><span class="lbl">Passcode</span><span class="val">{m['passcode']}</span></div>
      </div>
      <div class="zoom">{m['zoom_short']}</div>
    </div>
  </div>
  <div class="qr">
    <img src="{qr_uri}" alt="Zoom QR">
    <div class="cap">Scan to join</div>
  </div>
</body>
</html>
"""

    (TEMPLATES / "hoa-meeting.html").write_text(template)
    print(f"Wrote templates/hoa-meeting.html ({len(template)} bytes)")

    png_data = render_html("hoa-meeting.html")
    img = Image.open(io.BytesIO(png_data)).convert("RGB")
    img = img.resize((800, 480), Image.LANCZOS)
    solid = img.quantize(palette=SPECTRA6_PALETTE, dither=Image.Dither.NONE)

    solid.convert("RGB").save(HERE / "hoa_preview.png")
    print("Wrote hoa_preview.png (solid colors)")

    (HERE / "hoa-meeting.bin").write_bytes(pack_nibbles(solid))
    print("Wrote hoa-meeting.bin (192000 bytes)")


if __name__ == "__main__":
    main()
