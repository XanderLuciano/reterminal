"""
Weather Provider — fetches real data from US National Weather Service API (no key needed).

Falls back to cached/mock data if the API is unreachable.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlopen, Request

HERE = Path(__file__).parent
CACHE_FILE = HERE / "weather_cache.json"
CACHE_TTL = timedelta(minutes=10)  # re-fetch after 10 min

# NWS grid point — change these to your location
# Find yours: https://api.weather.gov/points/{lat},{lng}
GRID_ID = "LOX"
GRID_X = 134
GRID_Y = 59
LOCATION_NAME = "Moorpark, CA"  # displayed in templates
LAT = 34.2856
LNG = -118.8820

NWS_BASE = "https://api.weather.gov"
SUNRISE_API = "https://api.sunrise-sunset.org/json"

# Map NWS shortForecast keywords to display icons
FORECAST_ICON_MAP = {
    "sunny": "☀️",
    "clear": "☀️",
    "mostly clear": "🌤",
    "mostly sunny": "🌤",
    "partly cloudy": "⛅",
    "partly sunny": "⛅",
    "mostly cloudy": "☁️",
    "cloudy": "☁️",
    "overcast": "☁️",
    "rain": "🌧",
    "rain likely": "🌧",
    "chance rain": "🌦",
    "slight chance rain": "🌦",
    "showers": "🌧",
    "thunderstorms": "⛈",
    "chance thunderstorms": "⛈",
    "fog": "🌫",
    "patchy fog": "🌫",
    "haze": "🌫",
    "smoke": "🌫",
    "windy": "💨",
    "breezy": "💨",
    "snow": "❄️",
    "sleet": "🌨",
}

SKY_COLOR_MAP = {
    "sunny": "#ff6600",
    "clear": "#ff6600",
    "mostly clear": "#ff8800",
    "mostly sunny": "#ff8800",
    "partly cloudy": "#666666",
    "partly sunny": "#666666",
    "mostly cloudy": "#444488",
    "cloudy": "#444488",
    "overcast": "#333366",
    "rain": "#4488aa",
    "showers": "#4488aa",
    "thunderstorms": "#883344",
    "fog": "#888888",
    "patchy fog": "#888888",
    "haze": "#888888",
    "windy": "#888888",
}

HUMIDITY_LABELS = [
    (30, "Dry"),
    (50, "Comfortable"),
    (70, "Slightly Humid"),
    (85, "Humid"),
    (100, "Very Humid"),
]


def _fetch_json(url: str) -> dict | None:
    """Fetch JSON with browser-like User-Agent (NWS requires it)."""
    try:
        req = Request(url, headers={"User-Agent": "E1002Dashboard/1.0 (moorpark, ca)"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[weather_provider] Fetch failed for {url}: {e}")
        return None


def _cached_or_fresh():
    """Return cached data if fresh, or None."""
    if CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            cached_time = datetime.fromisoformat(cached["_cached_at"])
            if datetime.now() - cached_time < CACHE_TTL:
                return cached
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return None


def _write_cache(data: dict):
    """Write data to cache."""
    data["_cached_at"] = datetime.now().isoformat()
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def _celsius_to_f(c: float | None) -> int:
    if c is None:
        return "--"
    return round(c * 9 / 5 + 32)


def _mph_to_label(mph: float | None) -> str:
    if mph is None:
        return "Calm"
    if mph < 1:
        return "Calm"
    if mph < 5:
        return "Light"
    if mph < 15:
        return "Breezy"
    if mph < 25:
        return "Windy"
    if mph < 35:
        return "Strong"
    return "Gusty"


def _humidity_label(h: float | None) -> str:
    if h is None:
        return "—"
    for threshold, label in HUMIDITY_LABELS:
        if h <= threshold:
            return label
    return "Very Humid"


def _get_icon(short_forecast: str) -> str:
    """Map NWS short forecast to icon."""
    sf = short_forecast.lower().strip()
    # Try exact match first
    for key, icon in FORECAST_ICON_MAP.items():
        if key in sf:
            return icon
    return "🌡"


def _get_sky_color(short_forecast: str) -> str:
    sf = short_forecast.lower().strip()
    for key, color in SKY_COLOR_MAP.items():
        if key in sf:
            return color
    return "#111111"


def _get_temp_color(temp_f: int | str) -> str:
    """Choose text color based on temperature sensation."""
    if isinstance(temp_f, str):
        return "#111111"
    if temp_f >= 100:
        return "#ff0000"  # hot = red
    if temp_f >= 85:
        return "#ff6600"  # warm = orange
    if temp_f >= 70:
        return "#111111"  # comfortable = black
    if temp_f >= 55:
        return "#0066ff"  # cool = blue
    return "#0000ff"  # cold = deep blue


def _uv_label(index: float | None) -> str:
    if index is None:
        return "—"
    if index <= 2:
        return "Low"
    if index <= 5:
        return "Moderate"
    if index <= 7:
        return "High"
    if index <= 10:
        return "Very High"
    return "Extreme"


def _uv_color(index: float | None) -> str:
    if index is None:
        return "#888888"
    if index <= 2:
        return "#00aa00"
    if index <= 5:
        return "#ffaa00"
    if index <= 7:
        return "#ff6600"
    if index <= 10:
        return "#ff0000"
    return "#cc00cc"


def _uv_bg(index: float | None) -> str:
    if index is None:
        return "#f5f5f5"
    if index <= 2:
        return "#f0fff0"
    if index <= 5:
        return "#fff8f0"
    if index <= 7:
        return "#fff0e0"
    return "#fff0f0"


# ── AQI helpers (EPA scale) ──

def _aqi_label(index: int | None) -> str:
    if index is None:
        return "—"
    if index <= 50:
        return "Good"
    if index <= 100:
        return "Moderate"
    if index <= 150:
        return "Unhealthy Sens."
    if index <= 200:
        return "Unhealthy"
    if index <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _aqi_color(index: int | None) -> str:
    if index is None:
        return "#888888"
    if index <= 50:
        return "#00aa00"
    if index <= 100:
        return "#cccc00"
    if index <= 150:
        return "#ff7e00"
    if index <= 200:
        return "#ff0000"
    if index <= 300:
        return "#8844aa"
    return "#7e0023"


def _aqi_bg(index: int | None) -> str:
    if index is None:
        return "#f5f5f5"
    if index <= 50:
        return "#f0fff0"
    if index <= 100:
        return "#fffff0"
    if index <= 150:
        return "#fff4e8"
    if index <= 200:
        return "#fff0f0"
    if index <= 300:
        return "#f8f0ff"
    return "#fff0f5"


def _daylight_pct(sunrise_dt, sunset_dt, now_dt) -> tuple[int, int]:
    """Calculate what percent of daylight has elapsed, and total daylight minutes."""
    sunrise_min = sunrise_dt.hour * 60 + sunrise_dt.minute
    sunset_min = sunset_dt.hour * 60 + sunset_dt.minute
    now_min = now_dt.hour * 60 + now_dt.minute

    daylight_minutes = sunset_min - sunrise_min
    if daylight_minutes <= 0:
        return 0, 0

    elapsed = max(0, min(daylight_minutes, now_min - sunrise_min))
    pct = int(elapsed / daylight_minutes * 100) if daylight_minutes > 0 else 0
    return pct, daylight_minutes


def _abbreviate_day(name: str) -> str:
    """Abbreviate an NWS day name to standard 3-letter form.
    
    NWS sometimes uses holiday names like 'Memorial Day' or 'Christmas'
    instead of weekday names.
    """
    name = name.strip()
    # Known full names -> short map
    FULL_MAP = {
        "Memorial Day": "Mon",
        "Thanksgiving": "Thu",
        "Thanksgiving Day": "Thu",
        "Christmas": "Wed",
        "Christmas Day": "Wed",
        "New Year's": "Tue",
        "New Year's Day": "Tue",
        "Independence Day": "Thu",
        "Labor Day": "Mon",
        "Washington's Birthday": "Mon",
        "Martin Luther King Jr Day": "Mon",
        "MLK Day": "Mon",
        "Veterans Day": "Wed",
        "Veteran's Day": "Wed",
        "Columbus Day": "Mon",
        "Indigenous Peoples' Day": "Mon",
    }
    if name in FULL_MAP:
        return FULL_MAP[name]
    # Generic: take first 3 chars
    parts = name.split()
    base = parts[0]
    return base[:3]


def fetch_weather() -> dict | None:
    """
    Fetch real weather data from NWS API.
    Returns a context dict matching the weather.html template, or None on failure.
    """
    cached = _cached_or_fresh()
    if cached and "weather_context" in cached:
        return cached["weather_context"]

    now = datetime.now()

    # 1. Fetch forecast
    forecast_url = f"{NWS_BASE}/gridpoints/{GRID_ID}/{GRID_X},{GRID_Y}/forecast"
    forecast_data = _fetch_json(forecast_url)
    if not forecast_data:
        return None

    periods = forecast_data.get("properties", {}).get("periods", [])

    # 2. Fetch hourly forecast for more granular data
    hourly_url = f"{NWS_BASE}/gridpoints/{GRID_ID}/{GRID_X},{GRID_Y}/forecast/hourly"
    hourly_data = _fetch_json(hourly_url)
    hourly_periods = hourly_data.get("properties", {}).get("periods", []) if hourly_data else []

    # 3. Get current conditions from nearest station (KCMA = Camarillo)
    obs_url = f"{NWS_BASE}/stations/KCMA/observations/latest"
    obs_data = _fetch_json(obs_url)

    # 4. Get sunrise/sunset
    today_date = now.strftime("%Y-%m-%d")
    sunset_url = f"{SUNRISE_API}?lat={LAT}&lng={LNG}&date={today_date}&formatted=0"
    sunrise_data = _fetch_json(sunset_url)

    # ── Parse current conditions ──
    current_temp_f = None
    current_humidity = None
    current_wind_speed = None
    current_wind_dir = None
    current_sky = "—"
    current_icon = "🌡"

    if obs_data:
        props = obs_data.get("properties", {})
        if props.get("temperature", {}).get("value") is not None:
            current_temp_f = _celsius_to_f(props["temperature"]["value"])
            current_humidity = round(props.get("relativeHumidity", {}).get("value", 0), 0)
            if props.get("windSpeed", {}).get("value") is not None:
                current_wind_speed = round(props["windSpeed"]["value"] * 2.237)  # m/s → mph
            if props.get("windDirection", {}).get("value") is not None:
                wd = props["windDirection"]["value"]
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                current_wind_dir = dirs[round(wd / 22.5) % 16]

    # Use hourly period data as fallback for sky/icon
    if hourly_periods and current_sky == "—":
        hp = hourly_periods[0]
        current_sky = hp.get("shortForecast", "—")
        current_icon = _get_icon(current_sky)

    # ── Parse high/low from daytime periods ──
    today_high = None
    today_low = None
    forecast_days = []

    # Collect daytime periods with their corresponding nighttime lows
    for i, p in enumerate(periods):
        temp = p["temperature"]
        if p["isDaytime"]:
            if today_high is None:
                today_high = temp
        else:
            if today_low is None:
                today_low = temp

    # Build 5-day forecast from forecast periods (daytime)
    day_periods = [p for p in periods if p["isDaytime"]]
    night_periods = [p for p in periods if not p["isDaytime"]]

    for i in range(min(5, len(day_periods))):
        dp = day_periods[i]
        low_temp = None
        if i < len(night_periods):
            low_temp = night_periods[i]["temperature"]
        elif i + 1 < len(night_periods):
            low_temp = night_periods[i + 1]["temperature"]

        icon_key = dp["shortForecast"]
        forecast_days.append({
            "name": _abbreviate_day(dp["name"]),
            "icon": _get_icon(icon_key),
            "high": dp["temperature"],
            "low": low_temp if low_temp else "—",
        })

    # ── Parse sunrise/sunset ──
    sunrise_str = "—"
    sunset_str = "—"
    daylight_pct = 48  # default to roughly noon
    daylight_hrs = "—"

    if sunrise_data and sunrise_data.get("status") == "OK":
        sr = sunrise_data["results"]
        # Convert UTC to local
        sunrise_utc = datetime.fromisoformat(sr["sunrise"].replace("Z", "+00:00"))
        sunset_utc = datetime.fromisoformat(sr["sunset"].replace("Z", "+00:00"))

        local_tz = datetime.now(timezone(timedelta(hours=-7))).astimezone().tzinfo

        sunrise_local = sunrise_utc.replace(tzinfo=timezone.utc).astimezone()
        sunset_local = sunset_utc.replace(tzinfo=timezone.utc).astimezone()

        sunrise_str = sunrise_local.strftime("%I:%M %p").lstrip("0")
        sunset_str = sunset_local.strftime("%I:%M %p").lstrip("0")

        now_local = datetime.now().astimezone()
        daylight_pct, daylight_min = _daylight_pct(sunrise_local, sunset_local, now_local)
        daylight_hrs = f"{daylight_min // 60}h {daylight_min % 60}m"

    current_dt_str = now.strftime("%I:%M %p").lstrip("0")

    # UV index — fetch from Open-Meteo (free, no key)
    uv_index = None
    aqi = None
    aqi_pm25 = None
    aqi_pm10 = None
    aqi_pollutant = "—"

    # Fetch UV + AQI in one call (Open-Meteo air quality has UV too, but separate endpoints)
    uv_data = _fetch_json(
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=" + str(LAT) + "&longitude=" + str(LNG) + "&current=uv_index&timezone=America%2FLos_Angeles"
    )
    if uv_data and "current" in uv_data:
        uv_index = uv_data["current"].get("uv_index")

    # Fetch AQI from Open-Meteo Air Quality API (free, no key)
    aqi_data = _fetch_json(
        "https://air-quality-api.open-meteo.com/v1/air-quality?"
        "latitude=" + str(LAT) + "&longitude=" + str(LNG) + "&current=us_aqi,us_aqi_pm2_5,us_aqi_pm10"
    )
    if aqi_data and "current" in aqi_data:
        aqi = aqi_data["current"].get("us_aqi")
        aqi_pm25 = aqi_data["current"].get("us_aqi_pm2_5")
        aqi_pm10 = aqi_data["current"].get("us_aqi_pm10")
        # Determine dominant pollutant
        if aqi_pm25 is not None and aqi_pm10 is not None:
            aqi_pollutant = "PM2.5" if aqi_pm25 >= aqi_pm10 else "PM10"
        elif aqi_pm25 is not None:
            aqi_pollutant = "PM2.5"
        elif aqi_pm10 is not None:
            aqi_pollutant = "PM10"

    # ── Build context ──
    context = {
        "location": LOCATION_NAME,
        "current": {
            "temp": current_temp_f if current_temp_f is not None else (today_high or "--"),
            "temp_color": _get_temp_color(current_temp_f) if current_temp_f else "#111111",
            "feels_like": current_temp_f if current_temp_f is not None else (today_high or "--"),
            "sky": current_sky,
            "sky_color": _get_sky_color(current_sky),
            "high": today_high if today_high is not None else "--",
            "low": today_low if today_low is not None else "--",
            "humidity": current_humidity if current_humidity is not None else "--",
            "humidity_label": _humidity_label(current_humidity),
            "wind_speed": current_wind_speed if current_wind_speed is not None else "--",
            "wind_dir": current_wind_dir if current_wind_dir else "—",
            "uv_index": uv_index if uv_index is not None else "—",
            "uv_color": _uv_color(uv_index),
            "uv_bg": _uv_bg(uv_index),
            "uv_label": _uv_label(uv_index),
            "aqi": aqi if aqi is not None else "—",
            "aqi_color": _aqi_color(aqi),
            "aqi_bg": _aqi_bg(aqi),
            "aqi_label": _aqi_label(aqi),
            "aqi_pollutant": aqi_pollutant,
            "sunrise": sunrise_str,
            "sunset": sunset_str,
            "daylight_pct": daylight_pct,
            "daylight_hours": daylight_hrs,
        },
        "forecast": forecast_days,
        "updated_at": current_dt_str,
        "battery": "—",  # filled by server
    }

    # Cache it
    _write_cache({"weather_context": context})
    return context


def clear_cache():
    """Force re-fetch on next call."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


if __name__ == "__main__":
    import pprint
    ctx = fetch_weather()
    if ctx:
        pprint.pprint(ctx)
    else:
        print("Failed to fetch weather data")
