"""
Firmware build handler for the web flasher.
Accepts config JSON, generates wifi_config.h + config overrides, runs pio run,
and returns merged firmware binary ready for esptool-js flashing.
"""
import json
import shutil
import subprocess
import threading
from pathlib import Path

HERE = Path(__file__).parent
FIRMWARE_DIR = HERE.parent / "firmware"
SRC_DIR = FIRMWARE_DIR / "src"

# Mapping: device ID → PlatformIO env name
DEVICE_ENVS = {
    "e1002": "seeed_xiao_esp32s3",
    "e1001": "reterminal_e1001",
}

# In-progress builds: {build_id: {"status": "building"|"done"|"error", "message": str, "files": dict}}
_builds: dict = {}
_builds_lock = threading.Lock()
_build_counter = 0


def _next_build_id() -> str:
    global _build_counter
    _build_counter += 1
    return f"build-{_build_counter:04d}"


def get_build_status(build_id: str) -> dict | None:
    with _builds_lock:
        return _builds.get(build_id)


def start_build(config: dict) -> str:
    """Kick off an async build, return build_id."""
    build_id = _next_build_id()
    with _builds_lock:
        _builds[build_id] = {"status": "queued", "message": "Build queued", "files": {}}

    thread = threading.Thread(target=_do_build, args=(build_id, config), daemon=True)
    thread.start()
    return build_id


def _do_build(build_id: str, config: dict):
    with _builds_lock:
        _builds[build_id]["status"] = "building"
        _builds[build_id]["message"] = "Generating configuration..."

    device = config.get("device", "e1002")
    env = DEVICE_ENVS.get(device)
    if not env:
        with _builds_lock:
            _builds[build_id] = {"status": "error", "message": f"Unknown device: {device}", "files": {}}
        return

    try:
        # 1. Write wifi_config.h
        _update("Writing WiFi config...", build_id)
        ssid = config.get("wifi_ssid", "YourWiFiNetwork")
        password = config.get("wifi_password", "YourWiFiPassword")
        _write_wifi_config(ssid, password)

        # 2. Backup and modify main.cpp with config overrides
        main_cpp = SRC_DIR / "main.cpp"
        backup_path = main_cpp.with_suffix(".cpp.webflasher.bak")

        # Read original
        original = main_cpp.read_text()

        # Apply config overrides
        patched = _patch_main_cpp(original, config, device)

        # Write patched version
        main_cpp.write_text(patched)

        # 3. Run PlatformIO build
        _update("Compiling firmware (this takes 1–2 minutes)...", build_id)
        result = subprocess.run(
            ["pio", "run", "-e", env],
            cwd=FIRMWARE_DIR,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min — cold PlatformIO builds need to download toolchains
        )

        # Restore original main.cpp immediately
        main_cpp.write_text(original)
        if backup_path.exists():
            backup_path.unlink()

        if result.returncode != 0:
            error_msg = result.stderr[-500:] if result.stderr else "Unknown build error"
            with _builds_lock:
                _builds[build_id] = {"status": "error", "message": f"Build failed:\n{error_msg}", "files": {}}
            return

        # 4. Locate build artifacts
        _update("Packaging firmware for flashing...", build_id)
        build_dir = FIRMWARE_DIR / ".pio" / "build" / env
        factory_bin = build_dir / "firmware.factory.bin"
        firmware = build_dir / "firmware.bin"

        if not factory_bin.exists():
            with _builds_lock:
                _builds[build_id] = {"status": "error", "message": "Missing build artifact: firmware.factory.bin", "files": {}}
            return

        # 5. Copy artifacts to a stable output dir, serve by build_id
        output_dir = HERE / "builds" / build_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # firmware.factory.bin is a complete image starting at 0x0
        # (includes bootloader, partitions, and firmware all at correct offsets)
        shutil.copy2(factory_bin, output_dir / "firmware.factory.bin")
        if firmware.exists():
            shutil.copy2(firmware, output_dir / "firmware.bin")

        # 6. Save the config used (for display)
        (output_dir / "config.json").write_text(json.dumps(config, indent=2))

        merged_size = factory_bin.stat().st_size

        with _builds_lock:
            _builds[build_id] = {
                "status": "done",
                "message": "Build complete",
                "files": {
                    "merged": f"/api/build/{build_id}/firmware.factory.bin",
                    "firmware": f"/api/build/{build_id}/firmware.bin",
                    "merged_size": merged_size,
                },
                "config": config,
            }

    except subprocess.TimeoutExpired:
        _restore_main_cpp()
        with _builds_lock:
            _builds[build_id] = {"status": "error", "message": "Build timed out (>3 minutes)", "files": {}}
    except Exception as e:
        _restore_main_cpp()
        with _builds_lock:
            _builds[build_id] = {"status": "error", "message": str(e), "files": {}}


def _update(message: str, build_id: str):
    with _builds_lock:
        if build_id in _builds:
            _builds[build_id]["message"] = message


def _escape_c_string(s: str) -> str:
    """Escape a string for safe inclusion in a C #define."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _write_wifi_config(ssid: str, password: str):
    config_path = SRC_DIR / "wifi_config.h"
    config_path.write_text(
        f"// wifi_config.h — Generated by web flasher\n"
        f"#pragma once\n\n"
        f'#define WIFI_SSID "{_escape_c_string(ssid)}"\n'
        f'#define WIFI_PASS "{_escape_c_string(password)}"\n'
    )


def _patch_main_cpp(source: str, config: dict, device: str) -> str:
    """Replace configurable constants in main.cpp with user values."""
    lines = source.split("\n")
    result = []

    for line in lines:
        # Deep sleep seconds
        if "const uint64_t DEEP_SLEEP_SECONDS" in line and "Deep sleep" not in line:
            val = config.get("deep_sleep_seconds", 60)
            result.append(f"const uint64_t DEEP_SLEEP_SECONDS = {val};")
        # BLE advertise timeout
        elif "const int ADVERTISE_TIMEOUT_S" in line:
            val = config.get("advertise_timeout_s", 10)
            result.append(f"const int ADVERTISE_TIMEOUT_S = {val};")
        # Health interval
        elif "const int HEALTH_INTERVAL_HOURS" in line:
            val = config.get("health_interval_hours", 6)
            result.append(f"const int HEALTH_INTERVAL_HOURS = {val};")
        # Select timeout
        elif "const int SELECT_TIMEOUT_S" in line:
            val = config.get("select_timeout_s", 30)
            result.append(f"const int SELECT_TIMEOUT_S = {val};")
        # Dashboard base URL
        elif 'const char* DASHBOARD_BASE_URL' in line:
            url = config.get("dashboard_url", "http://YOUR_SERVER_IP:8088")
            fb = "/dashboard.bin" if device == "e1002" else "/dashboard-bw.bin"
            full_url = url.rstrip("/") + fb
            result.append(f'  const char* DASHBOARD_BASE_URL = "{full_url}";')
        # BLE device names
        elif "#define BLE_DEVICE_NAME" in line:
            default_name = "E1001-Dashboard" if device == "e1001" else "E1002-Dashboard"
            name = config.get("ble_device_name", default_name)
            result.append(f'  #define BLE_DEVICE_NAME "{name}"')
        else:
            result.append(line)

    return "\n".join(result)


def _restore_main_cpp():
    """Restore main.cpp from backup if it exists."""
    main_cpp = SRC_DIR / "main.cpp"
    backup_path = main_cpp.with_suffix(".cpp.webflasher.bak")
    if backup_path.exists():
        shutil.copy2(backup_path, main_cpp)
        backup_path.unlink()
