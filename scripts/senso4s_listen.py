#!/usr/bin/env python3
"""Listen for Senso4s BLE beacons on macOS and print raw + decoded data."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

SENSO4S_MANUFACTURER_IDS = {0x0059, 0x09CC}
DEFAULT_SENSO4S_ADDRESS = "E0:5B:0F:C9:2D:B0"

USAGE_MODE = {
    1: "BBQ",
    2: "Camping",
    3: "Caravanning",
    4: "Heating",
    5: "Household",
}

LEVEL_SPECIAL = {
    251: "measurement_error",
    252: "scale_error",
    253: "sensor_error",
    254: "battery_critically_low",
    255: "calibration_required",
}


class Senso4sDecoder:
    @staticmethod
    def decode(payload: bytes) -> dict[str, Any]:
        decoded: dict[str, Any] = {
            "payload_len": len(payload),
            "raw_hex": payload.hex(),
        }

        if len(payload) < 12:
            decoded["error"] = "payload_too_short_for_full_decode"
            return decoded

        flags = payload[0]
        level_or_status = payload[1]
        battery_raw = payload[4]
        embedded_mac = payload[6:12]

        model_marker = (flags >> 4) & 0x0F
        usage_mode_code = flags & 0x0F

        decoded["flags"] = flags
        decoded["model_marker"] = model_marker
        decoded["model"] = "Basic" if model_marker == 0x8 else "Plus"
        decoded["usage_mode_code"] = usage_mode_code
        decoded["usage_mode"] = USAGE_MODE.get(usage_mode_code, f"unknown_{usage_mode_code}")
        decoded["battery_raw"] = battery_raw
        decoded["reserved_2"] = payload[2]
        decoded["reserved_3"] = payload[3]
        decoded["reserved_5"] = payload[5]
        decoded["embedded_mac"] = ":".join(f"{b:02X}" for b in embedded_mac)

        if 0 <= level_or_status <= 100:
            decoded["level_or_status_raw"] = level_or_status
            decoded["level_type"] = "gas_percent"
            decoded["gas_percent"] = level_or_status
        elif 241 <= level_or_status <= 247:
            flags_value = level_or_status - 240
            anomalies = []
            if flags_value & 0x01:
                anomalies.append("temperature")
            if flags_value & 0x02:
                anomalies.append("incline")
            if flags_value & 0x04:
                anomalies.append("motion")

            decoded["level_or_status_raw"] = level_or_status
            decoded["level_type"] = "anomaly"
            decoded["anomaly_flags"] = flags_value
            decoded["anomalies"] = anomalies
        elif level_or_status in LEVEL_SPECIAL:
            decoded["level_or_status_raw"] = level_or_status
            decoded["level_type"] = "special"
            decoded["special_status"] = LEVEL_SPECIAL[level_or_status]
        else:
            decoded["level_or_status_raw"] = level_or_status
            decoded["level_type"] = "unknown"

        return decoded


def format_iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Listen for Senso4s BLE beacons and print raw manufacturer data + decoded fields"
    )
    parser.add_argument(
        "--only-address",
        default=DEFAULT_SENSO4S_ADDRESS,
        help=(
            "Only print packets from this BLE MAC address (case-insensitive). "
            f"Default: {DEFAULT_SENSO4S_ADDRESS}"
        ),
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow duplicate advertisements (useful for live streaming)",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    only_address = args.only_address.lower() if args.only_address else None
    cb_options = {
        "use_bdaddr": True,
        "allow_duplicates": args.allow_duplicates,
    }

    def detection_callback(device: BLEDevice, adv: AdvertisementData) -> None:
        if only_address and device.address.lower() != only_address:
            return

        for company_id, manufacturer_bytes in adv.manufacturer_data.items():
            if company_id not in SENSO4S_MANUFACTURER_IDS:
                continue

            decoded = Senso4sDecoder.decode(manufacturer_bytes)
            raw_payload_hex = manufacturer_bytes.hex()
            full_manufacturer_hex = company_id.to_bytes(2, "little").hex() + raw_payload_hex

            print(
                f"[{format_iso_now()}] addr={device.address} name={device.name or '-'} "
                f"rssi={adv.rssi} company_id=0x{company_id:04X}"
            )
            print(f"  manufacturer_data_hex_payload={raw_payload_hex}")
            print(f"  manufacturer_data_hex_full={full_manufacturer_hex}")
            print("  decoded=")
            for key in sorted(decoded.keys()):
                print(f"    {key}: {decoded[key]}")
            print()

    scanner = BleakScanner(detection_callback=detection_callback, cb=cb_options)

    print("Listening for Senso4s beacons... Press Ctrl+C to stop.")
    print("Accepted manufacturer IDs: 0x0059, 0x09CC")
    print(f"Address filter: {args.only_address}")

    await scanner.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await scanner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopped.")
