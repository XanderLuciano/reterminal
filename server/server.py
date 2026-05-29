"""
E1002 Dashboard Server — Flask endpoint serving rendered+dithered dashboard images.

Usage:
    python server.py
    → http://localhost:8088/dashboard.png  (dithered for Spectra 6)
    → http://localhost:8088/preview.png    (full color preview without dithering)
"""
import io
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, request
from renderer import render_html, dither_spectra6, render_dashboard_raw, render_dashboard_raw_bw, dither_bw
from weather_provider import fetch_weather

HERE = Path(__file__).parent
app = Flask(__name__)

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
        "location": "Moorpark, CA",
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
                make_item("Fridge water filter", "2025-11-15", 180, "6mo interval"),
                make_item("Hot water tank flush", "2026-02-01", 365, "annual"),
                make_item("Dishwasher filter clean", "2026-04-10", 90),
                make_item("Washing machine drum clean", "2026-04-28", 60),
            ]
        },
        {
            "icon": "🌀", "name": "Air & Filters", "interval_label": "every 1–6 months",
            "tasks": [
                make_item("HVAC return filter", "2026-03-01", 90),
                make_item("Bathroom exhaust fan filter", "2026-01-10", 180),
                make_item("Range hood filter", "2026-05-01", 60),
            ]
        },
        {
            "icon": "🧹", "name": "Cleaning", "interval_label": "every 1–8 weeks",
            "tasks": [
                make_item("Deep clean bathrooms", "2026-05-10", 14),
                make_item("Oven deep clean", "2026-03-20", 90),
                make_item("Window tracks & sills", "2026-04-15", 60),
            ]
        },
        {
            "icon": "⚡", "name": "Safety & Seasonal", "interval_label": "every 3–12 months",
            "tasks": [
                make_item("Generator test run", "2026-05-01", 90),
                make_item("Smoke detector battery test", "2026-04-01", 180),
                make_item("Garage door lube & inspect", "2026-03-01", 180),
                make_item("Fire extinguisher check", "2026-02-15", 365),
            ]
        },
    ]

    # Count statuses
    overdue = sum(1 for s in sections for i in s["tasks"] if i["status"] == "overdue")
    soon = sum(1 for s in sections for i in s["tasks"] if i["status"] == "soon")
    good = sum(1 for s in sections for i in s["tasks"] if i["status"] == "good")

    return {
        "location": "Moorpark, CA",
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
            "lead_story": {
                "title": "E-Paper Display Goes Fully Wireless",
                "detail": "BLE push trigger confirmed working! ESP32 wakes from deep sleep, fetches dashboard over WiFi, and refreshes — all without a USB cable. Next: real API data.",
                "time": "BREAKING",
                "meta": "Moorpark, CA — firwmare fix deployed via PlatformIO",
            },
            "second_story": {
                "title": "Kitchen Renovation Nears Finish Line",
                "detail": "Cabinet handles ready for pickup at Home Depot. Countertop installation scheduled next. Final phase: backsplash and lighting.",
                "time": "IN PROGRESS",
                "meta": "67% complete — backsplash + lighting remain",
            },
            "weather": {
                "temp": 68,
                "feels_like": 65,
                "description": "Clear Skies",
                "humidity": 52,
                "wind": 5,
                "pollen": "7.2",
                "sunrise": "5:49 AM",
                "sunset": "7:55 PM",
            },
            "reminders": [
                {"text": "HOA contractor follow-up", "time": "Wed"},
                {"text": "Cheddar vet appointment", "time": "Fri 2pm"},
                {"text": "Cabinet handles — pick up", "time": "Soon"},
            ],
            "stats": {
                "tokens": "1.4M",
                "deepseek_spend": "$9.27",
                "active_agents": "3",
                "kitchen_reno": "67",
                "pihole_blocked": "0.1%",
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
            {"text": "Cheddar vet appointment", "time": "Fri 2pm", "priority": "later"},
        ],
        "cards": [
            {"icon": "🧠", "value": "1.2M", "label": "OpenClaw tokens today"},
            {"icon": "📡", "value": "$8.42", "label": "DeepSeek spend today"},
            {"icon": "⚡", "value": "3", "label": "Active sub-agents"},
            {"icon": "🔧", "value": "67%", "label": "Kitchen reno progress"},
        ],
        "status": {
            "line1": "🟢 NUC online",
            "line2": "🟢 Pi-Hole 0.1% blocked",
            "line3": "Updated " + now.strftime("%I:%M %p"),
        },
    }


# ── Routes ──

@app.route("/dashboard.png")
def dashboard_png():
    """Dithered dashboard ready for Spectra 6 ePaper display."""
    template = request.args.get("template", "newspaper")
    fname = f"{template}.html"
    battery = request.args.get("battery", "—")
    context = get_mock_context(fname, battery)
    png_data = render_html(fname, context)
    dithered = dither_spectra6(png_data)

    buf = io.BytesIO()
    dithered.convert("RGB").save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/preview.png")
def preview_png():
    """Full-color preview (before dithering) for design iteration."""
    template = request.args.get("template", "newspaper")
    battery = request.args.get("battery", "—")
    fname = f"{template}.html"
    context = get_mock_context(fname, battery)
    png_data = render_html(fname, context)
    return Response(png_data, mimetype="image/png")


@app.route("/dashboard.bin")
def dashboard_bin():
    """Raw nibble-packed binary for E1002 Spectra 6 color framebuffer.
    
    The ESP32 fetches this, memcpys it into the GxEPD2 buffer,
    then calls display.refresh(). No PNG decoding needed.
    """
    template = request.args.get("template", "newspaper")
    battery = request.args.get("battery", "—")
    fname = f"{template}.html"
    context = get_mock_context(fname, battery)
    raw = render_dashboard_raw(fname, context)
    return Response(raw, mimetype="application/octet-stream")


@app.route("/dashboard-bw.bin")
def dashboard_bw_bin():
    """Raw bit-packed binary for E1001 monochrome (BW) framebuffer.
    
    1-bit per pixel, 8 pixels per byte, MSB first.
    Same 800×480 resolution, just BW instead of 6-color.
    """
    template = request.args.get("template", "newspaper")
    battery = request.args.get("battery", "—")
    fname = f"{template}.html"
    context = get_mock_context(fname, battery)
    raw = render_dashboard_raw_bw(fname, context)
    return Response(raw, mimetype="application/octet-stream")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8088, debug=False)
