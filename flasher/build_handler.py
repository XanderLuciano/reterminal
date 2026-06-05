"""
Firmware build handler for the web flasher.
Accepts config JSON, generates wifi_config.h + config overrides, runs pio run,
and returns merged firmware binary ready for esptool-js flashing.

Build output is streamed line-by-line into the build state so the
frontend can show real-time progress instead of staring at a spinner.
"""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
FIRMWARE_DIR = HERE.parent / "firmware"
SRC_DIR = FIRMWARE_DIR / "src"

# Mapping: device ID → PlatformIO env name
DEVICE_ENVS = {
    "e1002": "seeed_xiao_esp32s3",
    "e1001": "reterminal_e1001",
}

# In-progress builds: {build_id: {"status": ..., "message": ..., "lines": [str], "files": dict}}
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
        _builds[build_id] = {
            "status": "queued",
            "message": "Build queued",
            "lines": [],
            "files": {},
        }

    thread = threading.Thread(target=_do_build, args=(build_id, config), daemon=True)
    thread.start()
    return build_id


def _push_line(build_id: str, line: str):
    """Append a line to the build log and update the status message."""
    with _builds_lock:
        if build_id not in _builds:
            return
        build = _builds[build_id]
        build.setdefault("lines", []).append(line)
        # Keep last 200 lines for memory
        if len(build["lines"]) > 200:
            build["lines"] = build["lines"][-200:]
        # Derive a brief status from the last meaningful line
        _derive_message(build, line)


def _derive_message(build: dict, line: str):
    """Extract a human-readable one-liner from PlatformIO output."""
    line_s = line.strip()

    # PlatformIO download progress lines: "Downloading... |█████▋    | 137/268 KB"
    if "Downloading" in line_s and ("|" in line_s or "KB" in line_s):
        build["message"] = line_s[:80]
        build["status"] = "building"
        return

    # Download status lines: "Library Manager: Installing ..."
    if "Installing" in line_s or "Unpacking" in line_s or "Already up-to-date" in line_s:
        build["message"] = line_s[:80]
        return

    # Tool download: "Downloading espressif/toolchain-xtensa-esp32s3@..."
    if line_s.startswith("Downloading") and "espressif" in line_s:
        name = line_s.split(" ")[1].split("@")[0].split("/")[-1]
        build["message"] = f"Downloading toolchain: {name}..."
        return

    # Compilation: "Compiling .pio/build/seeed_xiao_esp32s3/lib/..."
    if line_s.startswith("Compiling"):
        parts = line_s.split("/")
        if len(parts) > 2:
            # Show last few path components
            short = "/".join(parts[-3:])[:60]
            build["message"] = f"Compiling {short}..."
        return

    # Linker: "Linking .pio/build/..."
    if "Linking" in line_s:
        build["message"] = "Linking firmware..."
        return

    # Processing library: "Library Manager: Processing ..."
    if "Processing" in line_s and "Library" in line_s:
        build["message"] = line_s[:70]
        return

    # Error lines — keep them as the visible message
    if "error:" in line_s.lower() or "Error:" in line_s:
        build["message"] = line_s[:80]
        build["status"] = "error"
        return

    # Generic fallback for known PIO patterns
    if line_s and not line_s.startswith(" ") and not line_s.startswith("|") and len(line_s) > 10:
        build["message"] = line_s[:80]


def _do_build(build_id: str, config: dict):
    _push_line(build_id, "Generating configuration...")

    device = config.get("device", "e1002")
    env = DEVICE_ENVS.get(device)
    if not env:
        _push_line(build_id, f"ERROR: Unknown device '{device}'")
        with _builds_lock:
            if build_id in _builds:
                _builds[build_id]["status"] = "error"
        return

    try:
        # 1. Write wifi_config.h
        _push_line(build_id, "Writing WiFi config...")
        ssid = config.get("wifi_ssid", "YourWiFiNetwork")
        password = config.get("wifi_password", "YourWiFiPassword")
        _write_wifi_config(ssid, password)

        # 2. Backup and modify main.cpp with config overrides
        main_cpp = SRC_DIR / "main.cpp"
        backup_path = main_cpp.with_suffix(".cpp.webflasher.bak")

        original = main_cpp.read_text()
        patched = _patch_main_cpp(original, config, device)
        main_cpp.write_text(patched)

        # 3. Run PlatformIO build with live streaming
        _push_line(build_id, "Starting PlatformIO build...")

        process = subprocess.Popen(
            ["pio", "run", "-e", env],
            cwd=FIRMWARE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered
        )

        # Read lines until the process finishes
        start_time = time.time()
        build_timeout = 600  # 10 minutes
        returncode = None

        for raw_line in process.stdout:
            line = raw_line.rstrip("\n\r")
            _push_line(build_id, line)

            # Check timeout
            if time.time() - start_time > build_timeout:
                process.kill()
                _push_line(build_id, "TIMEOUT: Build exceeded 10 minutes")
                _push_line(build_id, "First-time PlatformIO builds download toolchains.")
                _push_line(build_id, "The container may need: pio platform install espressif32")
                _restore_main_cpp()
                with _builds_lock:
                    if build_id in _builds:
                        _builds[build_id]["status"] = "error"
                return

        process.wait()
        returncode = process.returncode

        # Restore original main.cpp immediately
        main_cpp.write_text(original)
        if backup_path.exists():
            backup_path.unlink()

        if returncode != 0:
            _push_line(build_id, "BUILD FAILED (see errors above)")
            with _builds_lock:
                if build_id in _builds:
                    _builds[build_id]["status"] = "error"
            return

        # 4. Locate build artifacts
        _push_line(build_id, "Build succeeded! Packaging firmware...")
        build_dir = FIRMWARE_DIR / ".pio" / "build" / env
        factory_bin = build_dir / "firmware.factory.bin"
        firmware = build_dir / "firmware.bin"

        if not factory_bin.exists():
            # PlatformIO didn't generate the merged image (older esptool, or
            # custom build config). Merge it ourselves from the components.
            _push_line(build_id, "factory.bin not found — merging from parts...")
            bootloader = build_dir / "bootloader.bin"
            partitions = build_dir / "partitions.bin"
            boot_app0 = build_dir / "boot_app0.bin"
            if not firmware.exists() or not bootloader.exists() or not partitions.exists():
                missing = []
                if not firmware.exists(): missing.append("firmware.bin")
                if not bootloader.exists(): missing.append("bootloader.bin")
                if not partitions.exists(): missing.append("partitions.bin")
                _push_line(build_id, f"ERROR: Missing build artifacts: {', '.join(missing)}")
                with _builds_lock:
                    if build_id in _builds:
                        _builds[build_id]["status"] = "error"
                return
            # Find esptool — search multiple locations for cross-platform compatibility.
            def _find_esptool():
                """Return (python_bin, esptool_path_or_flag) or (None, None)."""
                candidates = []

                # 1: System Python with esptool package (pip install esptool)
                # This is the most reliable path — works in Docker, Linux, macOS.
                for py in ("python3", "python"):
                    if shutil.which(py):
                        candidates.append((py, "-m esptool"))

                # 2: PlatformIO penv Python + tool-esptoolpy (modern installs)
                penv = Path.home() / ".platformio" / "penv" / "bin"
                for py_name in ("python3", "python"):
                    py = penv / py_name
                    if py.exists():
                        for ep in Path.home().glob(".platformio/packages/tool-esptoolpy/esptool.py"):
                            candidates.append((str(py), str(ep)))
                        break

                # 3: Python from pio shebang (pipx/venv installs)
                pio_bin = shutil.which("pio")
                if pio_bin:
                    try:
                        with open(pio_bin) as f:
                            shebang = f.readline().strip()
                        if shebang.startswith("#!") and "python" in shebang:
                            pio_python = shebang[2:].strip()
                            if Path(pio_python).exists():
                                candidates.append((pio_python, "-m esptool"))
                    except Exception:
                        pass

                # 4: Search for any esptool.py under .platformio
                for ep in Path.home().glob(".platformio/**/esptool.py"):
                    for py in ("python3", "python"):
                        if shutil.which(py):
                            candidates.append((py, str(ep)))
                            break
                        break

                # Try each candidate
                for py_bin, esptool_arg in candidates:
                    try:
                        if esptool_arg == "-m esptool":
                            test = subprocess.run(
                                [py_bin, "-m", "esptool", "--help"],
                                capture_output=True, text=True, timeout=10)
                        else:
                            test = subprocess.run(
                                [py_bin, esptool_arg, "--help"],
                                capture_output=True, text=True, timeout=10)
                        if test.returncode == 0 or "usage:" in test.stderr.lower():
                            return (py_bin, esptool_arg)
                    except Exception:
                        continue

                return (None, None)

            py_bin, esptool_arg = _find_esptool()
            if not py_bin:
                _push_line(build_id, "ERROR: Cannot find esptool — install PlatformIO or pip install esptool")
                with _builds_lock:
                    if build_id in _builds:
                        _builds[build_id]["status"] = "error"
                return

            _push_line(build_id, f"Merging flash image (via {py_bin} {esptool_arg})...")
            cmd_parts = [py_bin]
            if esptool_arg == "-m esptool":
                cmd_parts += ["-m", "esptool"]
            else:
                cmd_parts.append(esptool_arg)
            cmd_parts += [
                "--chip", "esp32s3", "merge-bin",
                "-o", str(factory_bin.absolute()),
                "--flash-mode", "dio", "--flash-size", "8MB",
                "0x0000", str(bootloader.absolute()),
                "0x8000", str(partitions.absolute()),
            ]
            # boot_app0.bin is at 0xe000, may be in build dir or framework dir
            boot_app0 = build_dir / "boot_app0.bin"
            if not boot_app0.exists():
                for fw_dir in Path.home().glob(".platformio/packages/framework-*/tools/partitions/boot_app0.bin"):
                    boot_app0 = fw_dir
                    break
            if boot_app0.exists():
                cmd_parts += ["0xe000", str(boot_app0.absolute())]
            cmd_parts += ["0x10000", str(firmware.absolute())]
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                err = result.stderr[-300:] if result.stderr else "Unknown error"
                _push_line(build_id, f"ERROR: esptool merge failed:\n{err}")
                with _builds_lock:
                    if build_id in _builds:
                        _builds[build_id]["status"] = "error"
                return
            _push_line(build_id, f"Merged image created: {factory_bin.stat().st_size / 1024:.0f} KB")

        # 5. Copy artifacts to output dir
        output_dir = HERE / "builds" / build_id
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(factory_bin, output_dir / "firmware.factory.bin")
        if firmware.exists():
            shutil.copy2(firmware, output_dir / "firmware.bin")
        (output_dir / "config.json").write_text(json.dumps(config, indent=2))

        merged_size = factory_bin.stat().st_size
        _push_line(build_id, f"Done — {merged_size / 1024:.0f} KB ready")

        with _builds_lock:
            if build_id in _builds:
                _builds[build_id].update({
                    "status": "done",
                    "message": f"Build complete ({merged_size / 1024:.0f} KB)",
                    "files": {
                        "merged": f"/api/build/{build_id}/firmware.factory.bin",
                        "firmware": f"/api/build/{build_id}/firmware.bin",
                        "merged_size": merged_size,
                    },
                    "config": config,
                })

    except Exception as e:
        _restore_main_cpp()
        _push_line(build_id, f"ERROR: {e}")
        with _builds_lock:
            if build_id in _builds:
                _builds[build_id]["status"] = "error"


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
        if "const uint64_t DEEP_SLEEP_SECONDS" in line and "Deep sleep" not in line:
            val = config.get("deep_sleep_seconds", 60)
            result.append(f"const uint64_t DEEP_SLEEP_SECONDS = {val};")
        elif "const int ADVERTISE_TIMEOUT_S" in line:
            val = config.get("advertise_timeout_s", 10)
            result.append(f"const int ADVERTISE_TIMEOUT_S = {val};")
        elif "const int HEALTH_INTERVAL_HOURS" in line:
            val = config.get("health_interval_hours", 6)
            result.append(f"const int HEALTH_INTERVAL_HOURS = {val};")
        elif "const int SELECT_TIMEOUT_S" in line:
            val = config.get("select_timeout_s", 30)
            result.append(f"const int SELECT_TIMEOUT_S = {val};")
        elif 'const char* DASHBOARD_BASE_URL' in line:
            url = config.get("dashboard_url", "http://YOUR_SERVER_IP:8088")
            fb = "/dashboard.bin" if device == "e1002" else "/dashboard-bw.bin"
            full_url = url.rstrip("/") + fb
            result.append(f'  const char* DASHBOARD_BASE_URL = "{full_url}";')
        elif "#define BLE_DEVICE_NAME" in line:
            default_name = "E1001-Dashboard" if device == "e1001" else "E1002-Dashboard"
            name = config.get("ble_device_name", default_name)
            result.append(f'  #define BLE_DEVICE_NAME "{name}"')
        elif "const bool ENABLE_BEEPS" in line:
            beeps = "true" if config.get("enable_beeps", True) else "false"
            result.append(f"const bool ENABLE_BEEPS = {beeps};")
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
