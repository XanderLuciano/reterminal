"""
E1002 Dashboard Renderer — HTML/CSS → PNG → Spectra 6 dithered image
Uses Playwright to render Jinja2 templates at 800x480, then dithers
for the 6-color Spectra 6 palette.
"""
import io
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

HERE = Path(__file__).parent
TEMPLATES = HERE / "templates"

# Spectra 6 palette (E Ink Spectra 6 full color: 6 colors)
# These are the actual displayable colors — everything gets dithered to these
SPECTRA6_PALETTE = Image.new("P", (1, 1))
SPECTRA6_PALETTE.putpalette([
    # Black      White      Yellow     Red        Blue       Green
    0x00,0x00,0x00,  0xFF,0xFF,0xFF,  0xFF,0xFF,0x00,  0xFF,0x00,0x00,  0x00,0x00,0xFF,  0x00,0xFF,0x00,
    # pad to 768 bytes (256 colors * 3)
    *([0]*((256-6)*3))
])


def render_html(template_name: str, context: dict | None = None) -> bytes:
    """Render a Jinja2 HTML template to a PNG screenshot at 800x480."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    template = env.get_template(template_name)
    html = template.render(**(context or {}))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 800, "height": 480})
        page.set_content(html)
        png_data = page.screenshot(full_page=False)
        browser.close()

    return png_data


def dither_spectra6(png_data: bytes) -> Image.Image:
    """Apply Floyd-Steinberg dithering to reduce image to 6-color Spectra 6 palette."""
    img = Image.open(io.BytesIO(png_data)).convert("RGB")
    img = img.resize((800, 480), Image.LANCZOS)

    # Quantize to 6-color palette with Floyd-Steinberg dithering
    dithered = img.quantize(
        palette=SPECTRA6_PALETTE,
        dither=Image.Dither.FLOYDSTEINBERG
    )

    return dithered


def render_dashboard(template_name: str = "dashboard.html", context: dict | None = None) -> bytes:
    """Full pipeline: HTML → screenshot → dither → PNG bytes."""
    png_data = render_html(template_name, context)
    dithered = dither_spectra6(png_data)

    buf = io.BytesIO()
    dithered.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


# ── Nibble packing for ESP32 direct framebuffer ingest ──

# GxEPD2_730c (Spectra 6) 4-bit color indices (must match GxEPD2 driver)
# 0=Black 1=White 2=Green 3=Blue 4=Red 5=Yellow
_SPECTRA6_RGB_TO_NIBBLE = {
    (0, 0, 0):       0,  # Black
    (255, 255, 255): 1,  # White
    (0, 255, 0):     2,  # Green
    (0, 0, 255):     3,  # Blue
    (255, 0, 0):     4,  # Red
    (255, 255, 0):   5,  # Yellow
}


def pack_nibbles(img: Image.Image) -> bytes:
    """
    Convert a dithered RGB image to GxEPD2 4-bit nibble-packed format.
    Two pixels per byte: high nibble = pixel at (x,y), low nibble = pixel at (x+1,y).
    
    Returns raw bytes ready for GxEPD2's drawImage() / framebuffer write.
    """
    # quantize() returns mode "P" (palette). Convert to RGB for pixel access.
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    pixels = img.load()
    buf = bytearray((w * h + 1) // 2)

    for i, (r, g, b) in enumerate(img.getdata()):
        nibble = _SPECTRA6_RGB_TO_NIBBLE.get((r, g, b))
        if nibble is None:
            nibble = _closest_nibble(r, g, b)

        if i % 2 == 0:
            buf[i // 2] = nibble << 4
        else:
            buf[i // 2] |= nibble

    return bytes(buf)


def _closest_nibble(r: int, g: int, b: int) -> int:
    """Find closest Spectra 6 palette color by Euclidean distance."""
    palette = [
        (0, 0, 0, 0),        # Black
        (255, 255, 255, 1),  # White
        (0, 255, 0, 2),      # Green
        (0, 0, 255, 3),      # Blue
        (255, 0, 0, 4),      # Red
        (255, 255, 0, 5),    # Yellow
    ]
    best, best_dist = 0, float('inf')
    for pr, pg, pb, pn in palette:
        dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
        if dist < best_dist:
            best_dist = dist
            best = pn
    return best


def render_dashboard_raw(template_name: str = "dashboard.html", context: dict | None = None) -> bytes:
    """Full pipeline: HTML → screenshot → dither → nibble-packed binary for ESP32 (Spectra 6 color)."""
    png_data = render_html(template_name, context)
    dithered = dither_spectra6(png_data)
    return pack_nibbles(dithered)


# ── Monochrome (BW) pipeline for E1001 / GxEPD2_BW displays ──

def dither_bw(png_data: bytes) -> Image.Image:
    """Floyd-Steinberg dither to 1-bit black & white."""
    img = Image.open(io.BytesIO(png_data)).convert("L")
    img = img.resize((800, 480), Image.LANCZOS)
    return img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


def pack_bits(img: Image.Image) -> bytes:
    """
    Convert a 1-bit BW image to GxEPD2 bit-packed format.
    8 pixels per byte, MSB first (leftmost pixel = bit 7).
    
    Returns raw bytes ready for GxEPD2_BW display buffer.
    """
    if img.mode != "1":
        img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    w, h = img.size
    buf = bytearray((w * h + 7) // 8)

    for i, pixel in enumerate(img.getdata()):
        # pixel is 0 (black) or 255 (white) in mode "1"
        if pixel == 0:
            buf[i // 8] |= 0x80 >> (i % 8)

    return bytes(buf)


def render_dashboard_raw_bw(template_name: str = "dashboard.html", context: dict | None = None) -> bytes:
    """Full pipeline: HTML → screenshot → BW dither → bit-packed binary for E1001."""
    png_data = render_html(template_name, context)
    dithered = dither_bw(png_data)
    return pack_bits(dithered)
