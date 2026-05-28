#!/usr/bin/env python3
"""
BLE trigger for E1002 ePaper dashboard.

Connects to the E1002's BLE GATT server and writes a trigger byte
to force an immediate dashboard refresh. Called by the Flask server
after rendering new content.

Usage:
    python3 ble_trigger.py
    python3 ble_trigger.py --name "E1002-Dashboard"
    python3 ble_trigger.py --scan-timeout 30
"""
import asyncio
import argparse
import sys
from bleak import BleakScanner, BleakClient

# Must match firmware
TARGET_NAME = "E1002-Dashboard"
SERVICE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
TRIGGER_UUID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


async def trigger_epaper(name: str = TARGET_NAME, scan_timeout: float = 25.0, connect_timeout: float = 10.0):
    """Scan for the E1002 by service UUID, connect, write trigger, disconnect."""

    # ── Scan by service UUID (more reliable than name) ──
    print(f"Scanning up to {scan_timeout}s for E1002...", file=sys.stderr)
    device = None
    stop_event = asyncio.Event()

    def detection_callback(dev, adv_data):
        nonlocal device
        if device is not None:
            return
        try:
            if hasattr(adv_data, 'service_uuids') and adv_data.service_uuids:
                for uuid in adv_data.service_uuids:
                    if str(uuid) == SERVICE_UUID:
                        device = dev
                        stop_event.set()
                        return
        except Exception:
            pass
        if dev.name and dev.name == name:
            device = dev
            stop_event.set()

    async def stop_after_timeout():
        await asyncio.sleep(scan_timeout)
        stop_event.set()

    async with BleakScanner(detection_callback, scanning_mode='active'):
        await stop_event.wait()

    if device is None:
        print(f"ERROR: E1002 not found in {scan_timeout}s. Is it awake and in range?",
              file=sys.stderr)
        return False

    print(f"Found {device.name or '(unnamed)'} ({device.address})", file=sys.stderr)

    # ── Connect & trigger ──
    try:
        async with BleakClient(device, timeout=connect_timeout) as client:
            print(f"Connected! Writing trigger...", file=sys.stderr)
            # Write any non-zero byte to trigger a refresh
            await client.write_gatt_char(TRIGGER_UUID, b"\x01", response=True)
            print("Trigger sent!", file=sys.stderr)
            return True
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Trigger E1002 ePaper BLE refresh")
    parser.add_argument("--name", default=TARGET_NAME, help="BLE device name")
    parser.add_argument("--scan-timeout", type=float, default=30.0, help="Max seconds to scan for device")
    parser.add_argument("--connect-timeout", type=float, default=10.0, help="BLE connection timeout")
    parser.add_argument("--retries", type=int, default=3, help="Retry count if not found")
    args = parser.parse_args()

    for attempt in range(args.retries):
        if attempt > 0:
            print(f"Retry {attempt + 1}/{args.retries}...", file=sys.stderr)
        success = asyncio.run(trigger_epaper(args.name, args.scan_timeout, args.connect_timeout))
        if success:
            print("OK")
            sys.exit(0)
        if attempt < args.retries - 1:
            import time
            time.sleep(2)  # Wait between retries (ESP32 deep-sleeps for 30s)

    print("FAILED after all retries", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
