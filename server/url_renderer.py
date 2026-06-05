"""
URL Page Renderer — fetches external URLs, screenshots at 800×480,
dithers for e-ink, caches results, and auto-refreshes on a schedule.

Configured via url_pages.json. Each page gets:
  GET /page/<name>.bin        — BW dithered framebuffer (E1001)
  GET /page/<name>_color.bin  — color nibble-packed framebuffer (E1002)
  GET /page/<name>.png        — preview image
"""
import io
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from renderer import (
    render_html, dither_spectra6, dither_bw,
    render_dashboard_raw, render_dashboard_raw_bw,
    pack_nibbles, pack_bits,
)

HERE = Path(__file__).parent
CONFIG_FILE = HERE / "url_pages.json"

# In-memory cache: {name: {"config": {...}, "bw_bin": bytes, "color_bin": bytes, "png": bytes, "last_fetch": datetime}}
_cache = {}
_lock = threading.Lock()
_shutdown = False


def load_config():
    """Load URL pages from config file. Returns list of page dicts."""
    if not CONFIG_FILE.exists():
        return []
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    return data.get("pages", [])


def _fetch_url(url: str) -> bytes | None:
    """Fetch a URL via Playwright and return an 800×480 PNG screenshot."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 800, "height": 480})
            page.goto(url, wait_until="networkidle", timeout=30000)
            png_data = page.screenshot(full_page=False)
            browser.close()
        return png_data
    except Exception as e:
        print(f"[url_renderer] Failed to fetch {url}: {e}")
        return None


def _render_page(page_config: dict):
    """Fetch and render a single URL page, updating the cache."""
    name = page_config["name"]
    url = page_config["url"]

    png_data = _fetch_url(url)
    if not png_data:
        return

    with _lock:
        _cache[name] = {
            "config": page_config,
            "bw_bin": render_dashboard_raw_bw_raw_png(png_data),
            "color_bin": render_dashboard_raw_raw_png(png_data),
            "png": png_data,
            "last_fetch": datetime.now(),
        }


def render_dashboard_raw_raw_png(png_data: bytes) -> bytes:
    """Dither raw PNG to Spectra 6 nibble-packed binary (E1002)."""
    dithered = dither_spectra6(png_data)
    return pack_nibbles(dithered)


def render_dashboard_raw_bw_raw_png(png_data: bytes) -> bytes:
    """Dither raw PNG to 1-bit packed binary (E1001)."""
    dithered = dither_bw(png_data)
    return pack_bits(dithered)


def get_page_binary(name: str, format: str = "bw") -> bytes | None:
    """Get cached binary for a URL page. Returns None if not found."""
    with _lock:
        if name not in _cache:
            return None
        if format == "color":
            return _cache[name].get("color_bin")
        return _cache[name].get("bw_bin")


def get_page_png(name: str) -> bytes | None:
    """Get cached screenshot PNG for a URL page."""
    with _lock:
        if name not in _cache:
            return None
        return _cache[name].get("png")


def get_page_meta(name: str) -> dict | None:
    """Get metadata for a URL page (last fetch time, etc.)."""
    with _lock:
        if name not in _cache:
            return None
        entry = _cache[name]
        return {
            "name": name,
            "url": entry["config"]["url"],
            "refresh_seconds": entry["config"]["refresh_seconds"],
            "last_fetch": entry["last_fetch"].isoformat() if entry.get("last_fetch") else None,
        }


def _refresh_loop():
    """Background thread: refresh URL pages on their configured schedule."""
    # Initial fetch for all enabled pages (don't block caller)
    pages = load_config()
    for page in pages:
        if not page.get("enabled", True):
            continue
        print(f"[url_renderer] Initial fetch: {page['name']}")
        _render_page(page)

    while not _shutdown:
        pages = load_config()
        for page in pages:
            if not page.get("enabled", True):
                continue
            name = page["name"]
            interval = page.get("refresh_seconds", 300)
            with _lock:
                entry = _cache.get(name)
                if entry and entry.get("last_fetch"):
                    elapsed = (datetime.now() - entry["last_fetch"]).total_seconds()
                    if elapsed < interval:
                        continue
            # Needs refresh
            print(f"[url_renderer] Refreshing {name} ({page['url']})")
            _render_page(page)
        time.sleep(10)  # check every 10 seconds


def start():
    """Start background refresh thread."""
    global _shutdown
    _shutdown = False

    pages = load_config()
    enabled = [p for p in pages if p.get("enabled", True)]
    print(f"[url_renderer] Loaded {len(pages)} URL page(s), {len(enabled)} enabled")

    # Start background thread (initial fetch happens there, doesn't block startup)
    t = threading.Thread(target=_refresh_loop, daemon=True)
    t.start()
    print("[url_renderer] Background refresh thread started")


def stop():
    global _shutdown
    _shutdown = True


def list_pages():
    """Return list of configured pages with metadata."""
    pages = load_config()
    result = []
    for p in pages:
        name = p["name"]
        meta = get_page_meta(name) or {}
        result.append({
            "name": name,
            "url": p.get("url", ""),
            "title": p.get("title", name),
            "interval_minutes": p.get("refresh_seconds", 300) // 60,
            "selector": p.get("selector", ""),
            "enabled": p.get("enabled", True),
            "rendered_at": meta.get("rendered_at"),
            "file_size": meta.get("file_size"),
        })
    return result


def create_page(name: str, config: dict) -> bool:
    """Create a new URL page. Returns True on success."""
    pages = load_config()
    # Check for duplicates
    for p in pages:
        if p["name"] == name:
            return False
    page = {
        "name": name,
        "url": config.get("url", ""),
        "title": config.get("title", name),
        "refresh_seconds": config.get("interval_minutes", 30) * 60,
        "selector": config.get("selector", ""),
        "enabled": True,
    }
    pages.append(page)
    _save_config(pages)
    # Trigger initial render in background thread (don't block request)
    threading.Thread(target=_render_page, args=(page,), daemon=True).start()
    return True


def update_page(name: str, config: dict) -> bool:
    """Update an existing URL page. Returns True on success."""
    pages = load_config()
    for i, p in enumerate(pages):
        if p["name"] == name:
            pages[i] = {
                "name": name,
                "url": config.get("url", p.get("url", "")),
                "title": config.get("title", p.get("title", name)),
                "refresh_seconds": config.get("interval_minutes", 30) * 60,
                "selector": config.get("selector", p.get("selector", "")),
                "enabled": p.get("enabled", True),
            }
            _save_config(pages)
            return True
    return False


def delete_page(name: str) -> bool:
    """Delete a URL page. Returns True on success."""
    pages = load_config()
    original_len = len(pages)
    pages = [p for p in pages if p["name"] != name]
    if len(pages) == original_len:
        return False
    _save_config(pages)
    # Remove from cache
    with _lock:
        _cache.pop(name, None)
    return True


def rerender_page(name: str) -> bool:
    """Force re-render of a page. Returns True if page found."""
    pages = load_config()
    for p in pages:
        if p["name"] == name:
            threading.Thread(target=_render_page, args=(p,), daemon=True).start()
            return True
    return False


def _save_config(pages: list):
    """Save page configuration to disk."""
    url_pages_path = HERE / "url_pages.json"
    url_pages_path.write_text(json.dumps({"pages": pages}, indent=2))
