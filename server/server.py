"""
E1002 Dashboard Server — Flask endpoint serving rendered+dithered dashboard images.

Usage:
    python server.py
    → http://localhost:8088/dashboard.png  (dithered for Spectra 6)
    → http://localhost:8088/preview.png    (full color preview without dithering)
"""
import io
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, request, send_from_directory
from flask_cors import CORS
from renderer import render_html, dither_spectra6, render_dashboard_raw, render_dashboard_raw_bw, dither_bw
from weather_provider import fetch_weather
from url_renderer import get_page_binary, get_page_png, get_page_meta, start as start_url_renderer, list_pages, create_page, update_page, delete_page, rerender_page

# Import build handler for web flasher
sys.path.insert(0, str(Path(__file__).parent.parent / "flasher"))
from build_handler import start_build, get_build_status

HERE = Path(__file__).parent
app = Flask(__name__)
CORS(app)  # Allow Nuxt dev server (localhost:3000) to call API

# ── Real weather data (via NWS API, no key needed) ──

def get_weather_context(battery="87"):
    ctx = fetch_weather()
    if ctx:
        ctx["battery"] = battery
        return ctx
    # Fallback if API fails
    return _fallback_weather(battery)


def _fallback_weather(battery="87"):
    """Static fallback when API is unreachable."""
    now = datetime.now()
    sunrise_hr, sunrise_min = 5, 49
    sunset_hr, sunset_min = 19, 55
    daylight_minutes = (sunset_hr * 60 + sunset_min) - (sunrise_hr * 60 + sunrise_min)
    now_minutes = now.hour * 60 + now.minute
    elapsed = max(0, min(daylight_minutes, now_minutes - (sunrise_hr * 60 + sunrise_min)))
    daylight_pct = int(elapsed / daylight_minutes * 100) if daylight_minutes > 0 else 0

    return {
        "location": "Your Town, USA",
        "current": {
            "temp": "--",
            "temp_color": "#888888",
            "feels_like": "--",
            "sky": "Offline",
            "sky_color": "#888888",
            "high": "--",
            "low": "--",
            "humidity": "--",
            "humidity_label": "—",
            "wind_speed": "--",
            "wind_dir": "—",
            "uv_index": "—",
            "uv_color": "#888888",
            "uv_bg": "#f5f5f5",
            "uv_label": "—",
            "aqi": "—",
            "aqi_color": "#888888",
            "aqi_bg": "#f5f5f5",
            "aqi_label": "—",
            "aqi_pollutant": "—",
            "sunrise": f"{sunrise_hr}:{sunrise_min:02d} AM",
            "sunset": f"{sunset_hr}:{sunset_min:02d} PM",
            "daylight_pct": daylight_pct,
            "daylight_hours": f"{daylight_minutes // 60}h {daylight_minutes % 60}m",
        },
        "forecast": [
            {"name": "—", "icon": "🌡", "high": "--", "low": "--"},
        ],
        "updated_at": now.strftime("%I:%M %p"),
        "battery": battery,
    }


def get_maintenance_context(battery="87"):
    now = datetime.now()

    # Generate relative dates so they never go stale
    from datetime import timedelta
    def rel_date(days_ago_val):
        return (now - timedelta(days=days_ago_val)).strftime("%Y-%m-%d")

    def days_ago(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (now - d).days

    def calc_status(last_date, interval_days):
        elapsed = days_ago(last_date)
        remaining = interval_days - elapsed
        pct = min(100, int(elapsed / interval_days * 100))
        if remaining < 0:
            return "overdue", f"{-remaining}d OVERDUE", -remaining, pct
        elif remaining <= interval_days * 0.2:
            return "soon", f"{remaining}d left", remaining, pct
        else:
            return "good", f"{remaining}d left", remaining, pct

    def make_item(name, last_date, interval_days, extra=""):
        status, label, remaining, bar = calc_status(last_date, interval_days)
        last_fmt = datetime.strptime(last_date, "%Y-%m-%d").strftime("%b %d")
        return {
            "name": name,
            "last_done": last_fmt + (f" · {extra}" if extra else ""),
            "interval": interval_days,
            "days_remaining": remaining,
            "status": status,
            "status_label": "OVERDUE" if status == "overdue" else ("SOON" if status == "soon" else "OK"),
            "bar_pct": bar,
        }

    sections = [
        {
            "icon": "🔧", "name": "Appliances", "interval_label": "every 1–12 months",
            "tasks": [
                make_item("Fridge water filter", rel_date(200), 180, "6mo interval"),
                make_item("Hot water tank flush", rel_date(120), 365, "annual"),
                make_item("Dishwasher filter clean", rel_date(50), 90),
                make_item("Washing machine drum clean", rel_date(30), 60),
            ]
        },
        {
            "icon": "🌀", "name": "Air & Filters", "interval_label": "every 1–6 months",
            "tasks": [
                make_item("HVAC return filter", rel_date(90), 90),
                make_item("Bathroom exhaust fan filter", rel_date(140), 180),
                make_item("Range hood filter", rel_date(28), 60),
            ]
        },
        {
            "icon": "🧹", "name": "Cleaning", "interval_label": "every 1–8 weeks",
            "tasks": [
                make_item("Deep clean bathrooms", rel_date(18), 14),
                make_item("Oven deep clean", rel_date(70), 90),
                make_item("Window tracks & sills", rel_date(45), 60),
            ]
        },
        {
            "icon": "⚡", "name": "Safety & Seasonal", "interval_label": "every 3–12 months",
            "tasks": [
                make_item("Generator test run", rel_date(28), 90),
                make_item("Smoke detector battery test", rel_date(60), 180),
                make_item("Garage door lube & inspect", rel_date(90), 180),
                make_item("Fire extinguisher check", rel_date(105), 365),
            ]
        },
    ]

    # Count statuses
    overdue = sum(1 for s in sections for i in s["tasks"] if i["status"] == "overdue")
    soon = sum(1 for s in sections for i in s["tasks"] if i["status"] == "soon")
    good = sum(1 for s in sections for i in s["tasks"] if i["status"] == "good")

    return {
        "location": "Your Town, USA",
        "sections": sections,
        "summary": {"overdue": overdue, "soon": soon, "good": good},
        "updated_at": now.strftime("%I:%M %p"),
        "battery": battery,
    }


def get_mock_context(template_name="dashboard.html", battery="87"):
    now = datetime.now()

    if template_name == "maintenance.html":
        return get_maintenance_context(battery)

    if template_name == "weather.html":
        return get_weather_context(battery)  # uses real API data now

    if template_name == "newspaper.html":
        return {
            "date_long": now.strftime("%A, %B %d, %Y"),
            "issue_number": now.strftime("%j"),
            "location": "Your Town, USA",
            "lead_story": {
                "title": "E-Ink Dashboard Runs for Weeks on a Single Charge",
                "detail": "Wireless updates over WiFi with BLE push triggers. The 7.5-inch display draws zero power between refreshes — months of battery life from a 2000mAh cell.",
                "time": "TECH",
                "meta": "reTerminal E10xx · ESP32-S3 · PlatformIO · open-source firmware",
            },
            "second_story": {
                "title": "Open Source, Hackable, Yours to Customize",
                "detail": "Edit the HTML templates to change the layout. Tweak the Python server for your own data sources. Flash new firmware over USB in under a minute.",
                "time": "DIY",
                "meta": "Clone from github.com/XanderLuciano/reterminal",
            },
            "weather": {
                "temp": 72,
                "feels_like": 70,
                "description": "Partly Cloudy",
                "humidity": 48,
                "wind": 7,
                "pollen": "4.1",
                "sunrise": "6:12 AM",
                "sunset": "8:03 PM",
            },
            "reminders": [
                {"text": "Water the plants", "time": "Today"},
                {"text": "Team standup", "time": "10 AM"},
                {"text": "Grocery run", "time": "Evening"},
            ],
            "stats": {
                "tokens": "2.8M",
                "deepseek_spend": "$4.12",
                "active_agents": "2",
                "kitchen_reno": "100",
                "pihole_blocked": "3.2%",
            },
            "updated_at": now.strftime("%I:%M %p"),
            "battery": battery,
        }

    # Original dashboard template
    return {
        "time": now.strftime("%I:%M"),
        "date": now.strftime("%A, %B %d"),
        "weather": {
            "icon": "⛅",
            "temp": 72,
            "feels_like": 70,
            "description": "Partly Cloudy",
            "humidity": 58,
            "wind": 8,
            "pollen": "High",
            "pollen_index": "8.4/10",
            "pollen_level": "warn",
            "sunrise": "5:52 AM",
            "sunset": "7:58 PM",
        },
        "reminders": [
            {"text": "Kitchen cabinet handles — pick up from Home Depot", "time": "Today", "priority": "urgent"},
            {"text": "HOA waterproofing contractor follow-up", "time": "Wed", "priority": "soon"},
            {"text": "Grocery run", "time": "Evening", "priority": "later"},
        ],
        "cards": [
            {"icon": "🧠", "value": "2.4M", "label": "API tokens today"},
            {"icon": "📡", "value": "$3.15", "label": "API spend today"},
            {"icon": "⚡", "value": "3", "label": "Active sub-agents"},
            {"icon": "🔧", "value": "67%", "label": "Kitchen reno progress"},
        ],
        "status": {
            "line1": "🟢 NUC online",
            "line2": "🟢 Pi-Hole 0.1% blocked",
            "line3": "Updated " + now.strftime("%I:%M %p"),
        },
    }


def _format_battery(battery_raw: str) -> dict:
    """Convert battery param to display dict with state and label.
    
    Firmware sends: -1=charging, -2=full, >=0=battery pct.
    Returns: {'state': 'charging'|'full'|'battery', 'label': display string, 'pct': int|None}
    """
    try:
        val = int(battery_raw)
        if val == -1:
            return {"state": "charging", "label": "⚡", "pct": None}
        if val == -2:
            return {"state": "full", "label": "100%", "pct": 100}
        return {"state": "battery", "label": f"{val}%", "pct": val}
    except (ValueError, TypeError):
        return {"state": "battery", "label": str(battery_raw), "pct": None}


# ── Routes ──

@app.route("/dashboard.png")
def dashboard_png():
    """Dithered dashboard ready for Spectra 6 ePaper display."""
    template = request.args.get("template", "newspaper")
    fname = f"{template}.html"
    battery_info = _format_battery(request.args.get("battery", "—"))
    context = get_mock_context(fname, battery_info["label"])
    context["battery_info"] = battery_info
    dithered = dither_spectra6(png_data)

    buf = io.BytesIO()
    dithered.convert("RGB").save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/preview.png")
def preview_png():
    """Full-color preview (before dithering) for design iteration."""
    template = request.args.get("template", "newspaper")
    battery_info = _format_battery(request.args.get("battery", "—"))
    fname = f"{template}.html"
    context = get_mock_context(fname, battery_info["label"])
    context["battery_info"] = battery_info
    png_data = render_html(fname, context)
    return Response(png_data, mimetype="image/png")


def _etag_response(data: bytes, mimetype: str = "application/octet-stream"):
    """Return a Response with ETag header. Returns 304 if client's If-None-Match matches."""
    import hashlib
    etag = hashlib.md5(data).hexdigest()
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304)
    return Response(data, mimetype=mimetype, headers={"ETag": etag})


@app.route("/dashboard.bin")
def dashboard_bin():
    """Raw nibble-packed binary for E1002 Spectra 6 color framebuffer.
    
    Supports device-aware rendering:
    - ?device=ABC123&page=0 → look up device's assigned screens
    - ?template=newspaper → legacy (backward compatible)
    Unregistered devices get a "register me" page with QR code.
    """
    from device_db import get_device, get_device_screens, register_device

    device_id = request.args.get("device", "")
    page_n = request.args.get("page", "0")
    template = request.args.get("template", "")
    battery_info = _format_battery(request.args.get("battery", "—"))

    # Legacy mode: template= param (backward compatible)
    if not device_id and template:
        fname = f"{template}.html"
        context = get_mock_context(fname, battery_info["label"])
        context["battery_info"] = battery_info
        raw = render_dashboard_raw(fname, context)
        return _etag_response(raw, "application/octet-stream")

    # Device-aware mode: look up in DB
    if device_id:
        try:
            device = get_device(device_id)

            # Auto-adopt: register unknown device on first fetch
            if not device:
                device = register_device(device_id, "e1002")

            if not device:
                # DB not available — fall back to default page
                fname = "newspaper.html"
                context = get_mock_context("newspaper.html", battery_info["label"])
                context["battery_info"] = battery_info
                raw = render_dashboard_raw(fname, context)
                return _etag_response(raw, "application/octet-stream")

            # Get assigned screens for this device
            screens = get_device_screens(device_id)

            if not screens:
                # Device registered but no screens assigned — show registration info
                return _render_register_page(device_id, "e1002")

            # Serve the assigned screen at page index (wraps around)
            try:
                n = int(page_n) % len(screens)
            except ValueError:
                n = 0
            screen = screens[n]
            config = json.loads(screen["screen_config"])

            # Render based on screen type
            if screen["screen_type"] == "weather":
                ctx = get_weather_context(battery_info["label"])
                ctx["battery_info"] = battery_info
                raw = render_dashboard_raw("weather.html", ctx)
            elif screen["screen_type"] == "maintenance":
                ctx = get_maintenance_context(battery_info["label"])
                ctx["battery_info"] = battery_info
                raw = render_dashboard_raw("maintenance.html", ctx)
            elif screen["screen_type"] == "url":
                # URL screenshots rendered by url_renderer
                from url_renderer import get_page_binary
                data = get_page_binary(screen["screen_name"], "color")
                if data:
                    return _etag_response(data, "application/octet-stream")
                raw = render_dashboard_raw("newspaper.html", get_mock_context("newspaper.html", battery_info["label"]))
            else:
                # Default newspaper
                ctx = get_mock_context("newspaper.html", battery_info["label"])
                ctx["battery_info"] = battery_info
                raw = render_dashboard_raw("newspaper.html", ctx)

            return _etag_response(raw, "application/octet-stream")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[server] Device-aware render failed:\n{tb}")
            raw = _render_debug_error({
                "status_code": 500,
                "url": request.url,
                "device_id": device_id,
                "page": page_n,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_type": type(e).__name__,
                "exception": str(e),
                "body_preview": tb[-800:],
            }, "e1002")
            return _etag_response(raw, "application/octet-stream")

    # No device, no template — default to newspaper
    context = get_mock_context("newspaper.html", battery_info["label"])
    context["battery_info"] = battery_info
    raw = render_dashboard_raw("newspaper.html", context)
    return _etag_response(raw, "application/octet-stream")


@app.route("/dashboard-bw.bin")
def dashboard_bw_bin():
    """Raw bit-packed binary for E1001 monochrome (BW) framebuffer.
    
    Supports device-aware rendering:
    - ?device=ABC123&page=0 → look up device's assigned screens
    - ?template=newspaper → legacy (backward compatible)
    Unregistered devices get a "register me" page with QR code.
    """
    from device_db import get_device, get_device_screens, register_device

    device_id = request.args.get("device", "")
    page_n = request.args.get("page", "0")
    template = request.args.get("template", "")
    battery_info = _format_battery(request.args.get("battery", "—"))

    # Legacy mode: template= param (backward compatible)
    if not device_id and template:
        fname = f"{template}.html"
        context = get_mock_context(fname, battery_info["label"])
        context["battery_info"] = battery_info
        raw = render_dashboard_raw_bw(fname, context)
        return _etag_response(raw, "application/octet-stream")

    # Device-aware mode: look up in DB
    if device_id:
        try:
            device = get_device(device_id)

            # Auto-adopt: register unknown device on first fetch
            if not device:
                variant = request.args.get("variant", "e1001")
                device = register_device(device_id, variant)

            if not device:
                # DB not available — fall back to default page
                fname = "newspaper.html"
                context = get_mock_context("newspaper.html", battery_info["label"])
                context["battery_info"] = battery_info
                raw = render_dashboard_raw_bw(fname, context)
                return _etag_response(raw, "application/octet-stream")

            # Get assigned screens for this device
            screens = get_device_screens(device_id)

            if not screens:
                # Device registered but no screens assigned — show registration info
                return _render_register_page(device_id, "e1001")

            # Serve the assigned screen at page index (wraps around)
            try:
                n = int(page_n) % len(screens)
            except ValueError:
                n = 0
            screen = screens[n]
            config = json.loads(screen["screen_config"])

            # Render based on screen type
            if screen["screen_type"] == "weather":
                ctx = get_weather_context(battery_info["label"])
                ctx["battery_info"] = battery_info
                raw = render_dashboard_raw_bw("weather.html", ctx)
            elif screen["screen_type"] == "maintenance":
                ctx = get_maintenance_context(battery_info["label"])
                ctx["battery_info"] = battery_info
                raw = render_dashboard_raw_bw("maintenance.html", ctx)
            elif screen["screen_type"] == "url":
                # URL screenshots rendered by url_renderer
                from url_renderer import get_page_binary
                data = get_page_binary(screen["screen_name"], "bw")
                if data:
                    return _etag_response(data, "application/octet-stream")
                raw = render_dashboard_raw_bw("newspaper.html", get_mock_context("newspaper.html", battery_info["label"]))
            else:
                # Default newspaper
                ctx = get_mock_context("newspaper.html", battery_info["label"])
                ctx["battery_info"] = battery_info
                raw = render_dashboard_raw_bw("newspaper.html", ctx)

            return _etag_response(raw, "application/octet-stream")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[server] Device-aware render failed:\n{tb}")
            raw = _render_debug_error({
                "status_code": 500,
                "url": request.url,
                "device_id": device_id,
                "page": page_n,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_type": type(e).__name__,
                "exception": str(e),
                "body_preview": tb[-800:],
            }, "e1001")
            return _etag_response(raw, "application/octet-stream")

    # No device, no template — default to newspaper
    context = get_mock_context("newspaper.html", battery_info["label"])
    context["battery_info"] = battery_info
    raw = render_dashboard_raw_bw("newspaper.html", context)
    return _etag_response(raw, "application/octet-stream")


def _render_debug_error(info: dict, variant: str = "e1001") -> bytes:
    """Render a server error / debug page as a framebuffer binary.
    
    info keys: status_code, url, device_id, page, timestamp,
               error_type, exception, body_preview
    Returns raw framebuffer bytes for the device to display.
    """
    from renderer import render_dashboard_raw, render_dashboard_raw_bw
    if variant == "e1002":
        return render_dashboard_raw("debug_error.html", info)
    else:
        return render_dashboard_raw_bw("debug_error.html", info)


def _render_register_page(device_id: str, variant: str = "e1001") -> Response:
    """Render a registration instruction page with QR code."""
    try:
        import qrcode, io as io_mod, base64

        host = request.host
        register_url = f"http://{host}/devices?register={device_id}"

        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(register_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io_mod.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        qr_b64 = ""  # qrcode not installed — skip QR
        register_url = f"http://{host}/devices?register={device_id}"

    from renderer import render_dashboard_raw, render_dashboard_raw_bw
    ctx = {
        "device_id": device_id,
        "register_url": register_url,
        "qr_b64": qr_b64,
    }
    if variant == "e1002":
        raw = render_dashboard_raw("register.html", ctx)
    else:
        raw = render_dashboard_raw_bw("register.html", ctx)
    return _etag_response(raw, "application/octet-stream")


@app.route("/dashboard-bw.png")
def dashboard_bw_png():
    """BW-dithered PNG preview for E1001 (for design iteration)."""
    template = request.args.get("template", "newspaper")
    battery = request.args.get("battery", "—")
    fname = f"{template}.html"
    context = get_mock_context(fname, battery)
    png_data = render_html(fname, context)
    dithered = dither_bw(png_data)

    buf = io.BytesIO()
    dithered.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/trigger", methods=["POST", "GET"])
def trigger_refresh():
    """Push a BLE trigger to the E1002 for immediate refresh."""
    template = request.args.get("template", "newspaper")
    fname = f"{template}.html"
    battery = request.args.get("battery", "—")
    context = get_mock_context(fname, battery)
    render_dashboard_raw(fname, context)  # pre-render

    import subprocess, os
    script = os.path.join(os.path.dirname(__file__), "ble_trigger.py")
    try:
        subprocess.Popen(
            ["python3", script, "--name", "E1002-Dashboard", "--retries", "2"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        ble_status = "BLE trigger sent to E1002"
    except Exception as e:
        ble_status = f"BLE trigger failed: {e}"

    return {"status": "ok", "ble": ble_status, "message": f"Fresh {template} render ready for E1002"}


@app.route("/trigger-e1001", methods=["POST", "GET"])
def trigger_e1001_refresh():
    """Push a BLE trigger to the E1001 monochrome display."""
    template = request.args.get("template", "newspaper")
    fname = f"{template}.html"
    battery = request.args.get("battery", "—")
    context = get_mock_context(fname, battery)
    render_dashboard_raw_bw(fname, context)  # pre-render BW version

    import subprocess, os
    script = os.path.join(os.path.dirname(__file__), "ble_trigger.py")
    try:
        subprocess.Popen(
            ["python3", script, "--name", "E1001-Dashboard", "--retries", "2"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        ble_status = "BLE trigger sent to E1001"
    except Exception as e:
        ble_status = f"BLE trigger failed: {e}"

    return {"status": "ok", "ble": ble_status, "message": f"Fresh {template} BW render ready for E1001"}


# ── Demo pages (sample content for page manager previews) ──

@app.route("/demo/<name>")
def demo_page(name):
    """Serve demo HTML pages for sample e-ink page previews."""
    template_path = HERE / "templates" / f"demo-{name}.html"
    if template_path.exists():
        return template_path.read_text()
    return "Demo not found", 404


# ── URL Pages (external URL screenshots) ──

@app.route("/page/<name>.bin")
def url_page_bin(name):
    """BW-dithered framebuffer for a URL page (E1001)."""
    data = get_page_binary(name, "bw")
    if data is None:
        return {"error": f"URL page '{name}' not found or not yet rendered"}, 404
    return Response(data, mimetype="application/octet-stream")


@app.route("/page/<name>_color.bin")
def url_page_color_bin(name):
    """Color-dithered framebuffer for a URL page (E1002)."""
    data = get_page_binary(name, "color")
    if data is None:
        return {"error": f"URL page '{name}' not found or not yet rendered"}, 404
    return Response(data, mimetype="application/octet-stream")


@app.route("/page/<name>.png")
def url_page_png(name):
    """Preview PNG for a URL page."""
    data = get_page_png(name)
    if data is None:
        return {"error": f"URL page '{name}' not found or not yet rendered"}, 404
    return Response(data, mimetype="image/png")


@app.route("/page/<name>/meta")
def url_page_meta(name):
    """Metadata for a URL page."""
    meta = get_page_meta(name)
    if meta is None:
        return {"error": f"URL page '{name}' not found"}, 404
    return meta


@app.route("/pages")
def list_url_pages():
    """List all configured URL pages."""
    pages = list_pages()
    return {"pages": pages, "count": len(pages)}


# ── URL Page CRUD ──

@app.route("/page/<name>", methods=["POST"])
def api_create_page(name):
    """Create a new URL page."""
    config = request.get_json(force=True)
    if not config:
        return {"error": "Request body required"}, 400
    if create_page(name, config):
        return {"status": "ok", "name": name}
    return {"error": f"Page '{name}' already exists"}, 409


@app.route("/page/<name>", methods=["PUT"])
def api_update_page(name):
    """Update an existing URL page."""
    config = request.get_json(force=True)
    if not config:
        return {"error": "Request body required"}, 400
    if update_page(name, config):
        return {"status": "ok", "name": name}
    return {"error": f"Page '{name}' not found"}, 404


@app.route("/page/<name>", methods=["DELETE"])
def api_delete_page(name):
    """Delete a URL page."""
    if delete_page(name):
        return {"status": "ok"}
    return {"error": f"Page '{name}' not found"}, 404


@app.route("/page/<name>/refresh", methods=["POST"])
def api_rerender_page(name):
    """Force re-render of a URL page."""
    if rerender_page(name):
        return {"status": "ok"}
    return {"error": f"Page '{name}' not found"}, 404


# ── Web Flasher UI ──

FLASHER_DIR = HERE.parent / "flasher"
PREBUILT_DIR = FLASHER_DIR / "prebuilt"

PREBUILT_META = {
    "e1002": {
        "label": "E1002 (Spectra 6 · Color)",
        "file": "e1002-factory.bin",
        "size": None,  # filled at request time
        "note": "WiFi: test/test — will show error screen"
    },
    "e1001": {
        "label": "E1001 (Monochrome · BW)",
        "file": "e1001-factory.bin",
        "size": None,
        "note": "WiFi: test/test — will show error screen"
    },
}


@app.route("/api/prebuilt")
def api_prebuilt_list():
    """List available pre-built firmware images."""
    result = {}
    for variant, meta in PREBUILT_META.items():
        path = PREBUILT_DIR / meta["file"]
        info = dict(meta)
        info["size"] = path.stat().st_size if path.exists() else 0
        info["available"] = path.exists()
        result[variant] = info
    return result


@app.route("/prebuilt/<variant>")
def prebuilt_download(variant):
    """Download a pre-built firmware binary."""
    if variant not in PREBUILT_META:
        return {"error": f"Unknown variant: {variant}"}, 404
    path = PREBUILT_DIR / PREBUILT_META[variant]["file"]
    if not path.exists():
        return {"error": "Pre-built image not found"}, 404
    return send_from_directory(str(PREBUILT_DIR), PREBUILT_META[variant]["file"],
                               mimetype="application/octet-stream")


@app.route("/flasher")
@app.route("/flasher/")
def flasher_ui():
    return send_from_directory(str(FLASHER_DIR), "index.html")


# ── Build API ──

@app.route("/api/build", methods=["POST"])
def api_start_build():
    """Start a firmware build with the given config."""
    config = request.get_json(force=True)
    build_id = start_build(config)
    return {"build_id": build_id, "status": "started"}


@app.route("/api/build/<build_id>")
def api_build_status(build_id):
    """Poll build status."""
    status = get_build_status(build_id)
    if status is None:
        return {"error": "Build not found"}, 404
    return status


@app.route("/api/build/<build_id>/<path:filename>")
def api_build_download(build_id, filename):
    """Download a build artifact."""
    build_dir = FLASHER_DIR / "builds" / build_id
    if not build_dir.exists():
        return {"error": "Build not found"}, 404
    return send_from_directory(str(build_dir), filename)


# ── Global error handler for E-Ink binary routes ──
# Catches unhandled exceptions and returns a debug page as a valid framebuffer

@app.errorhandler(500)
def handle_500(e):
    """Render 500 errors as debug framebuffer pages."""
    path = request.path
    # Only intercept binary routes (other routes just return JSON error)
    if not path.endswith(".bin"):
        return {"error": str(e)}, 500
    
    tb = traceback.format_exc()
    device_id = request.args.get("device", "unknown")
    variant = "e1002" if path == "/dashboard.bin" else "e1001"
    info = {
        "status_code": 500,
        "url": request.url,
        "device_id": device_id,
        "page": request.args.get("page", "?"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error_type": type(e).__name__ if hasattr(e, "__cause__") else "InternalError",
        "exception": str(e)[:200],
        "body_preview": tb[-800:],
    }
    raw = _render_debug_error(info, variant)
    return Response(raw, mimetype="application/octet-stream", status=200)


if __name__ == "__main__":
    start_url_renderer()
    # Pre-warm weather cache on startup so first ESP32 request doesn't timeout
    import threading
    def _prewarm():
        print("[server] Pre-warming weather cache...")
        from weather_provider import fetch_weather
        ctx = fetch_weather()
        if ctx:
            print(f"[server] Weather cache ready ({ctx['current']['temp']}°F, {ctx['current']['sky']})")
        else:
            print("[server] Weather pre-warm failed (will use fallback)")
    threading.Thread(target=_prewarm, daemon=True).start()
    app.run(host="0.0.0.0", port=8088, debug=False)
