"""Push the local snake source files to an ESP32 over BLE OTA.

Run from the repo root:

    uv run python scripts/ble_push.py                 # full sync
    uv run python scripts/ble_push.py --dry-run       # just print the frame stream
    uv run python scripts/ble_push.py --name foo      # match a different advertised name
    uv run python scripts/ble_push.py --timeout 20    # scan for up to 20s
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Make ble_protocol importable without installing the embedded code as a package.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "embedded"))

from ble_protocol import (  # noqa: E402
    OP_ACK,
    OP_BEGIN_FILE,
    OP_COMMIT,
    OP_COMMITTED,
    OP_END_FILE,
    OP_FILE_CHUNK,
    OP_MANIFEST,
    OP_NACK,
    OP_READY,
    decode_frame,
    encode_session,
    parse_begin_file,
)

OP_NAMES = {
    OP_BEGIN_FILE: "BEGIN_FILE",
    OP_FILE_CHUNK: "FILE_CHUNK",
    OP_END_FILE: "END_FILE",
    OP_MANIFEST: "MANIFEST",
    OP_COMMIT: "COMMIT",
    OP_ACK: "ACK",
    OP_NACK: "NACK",
    OP_READY: "READY",
    OP_COMMITTED: "COMMITTED",
}


def collect_files(repo_root):
    """Walk src/embedded/*.py and src/common/**/*.py.

    Returns [(device_path, bytes)] where device_path is the on-device path:
    - `src/embedded/main.py` -> `main.py`
    - `src/common/engine.py` -> `common/engine.py`
    """
    repo_root = Path(repo_root)
    out = []
    embedded = repo_root / "src" / "embedded"
    if embedded.exists():
        for p in sorted(embedded.glob("*.py")):
            out.append((p.name, p.read_bytes()))
    common = repo_root / "src" / "common"
    if common.exists():
        for p in sorted(common.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(common)
            out.append(("common/" + str(rel).replace("\\", "/"), p.read_bytes()))
    return out


def _print_frame(frame):
    op, seq, payload = decode_frame(frame)
    name = OP_NAMES.get(op, f"OP_{op:02X}")
    extra = ""
    if op == OP_BEGIN_FILE:
        path, size, crc = parse_begin_file(payload)
        extra = " path=" + path + " size=" + str(size) + " crc=" + hex(crc)
    elif op == OP_MANIFEST:
        extra = " paths=" + repr(payload.decode("utf-8").split("\n"))
    elif op == OP_FILE_CHUNK:
        extra = " bytes=" + str(len(payload))
    print(f"seq={seq:3d} {name}{extra}")


def main_sync(argv):
    """Synchronous entrypoint. Returns process exit code."""
    parser = argparse.ArgumentParser(prog="ble_push", description="Push snake .py files over BLE OTA.")
    parser.add_argument("--name", default=None, help="advertised device name (default: from config.py)")
    parser.add_argument("--dry-run", action="store_true", help="encode and print frames without connecting")
    parser.add_argument("--timeout", type=float, default=10.0, help="scan/connect timeout seconds")
    parser.add_argument("--repo-root", default=str(ROOT), help="path to repo root (default: parent of scripts/)")
    args = parser.parse_args(argv)

    files = collect_files(args.repo_root)
    if not files:
        print("No files found under src/embedded or src/common; nothing to push.", file=sys.stderr)
        return 2

    if args.dry_run:
        for frame in encode_session(files):
            _print_frame(frame)
        return 0

    return asyncio.run(_push_async(files, args.name, args.timeout))


async def _push_async(files, name, timeout, transport=None):
    """Drive a sync session over the given transport. Returns process exit code."""
    if transport is None:
        transport = _BleakTransport()

    completed = asyncio.Event()
    failed = {"flag": False, "reason": None}

    def on_status(frame):
        op, seq, payload = decode_frame(frame)
        if op == OP_COMMITTED:
            print("device: COMMITTED")
            completed.set()
        elif op == OP_NACK:
            reason = payload[1] if len(payload) >= 2 else 0
            failed["flag"] = True
            failed["reason"] = reason
            print(
                f"device: NACK reason=0x{reason:02x} ({_nack_name(reason)})",
                file=sys.stderr,
            )
            completed.set()
        elif op == OP_READY:
            print("device: READY")
        elif op == OP_ACK:
            pass  # ignore for now
        else:
            print(f"device: unknown op 0x{op:02x}")

    transport.on_status(on_status)
    try:
        await transport.connect(name=name or _default_device_name(), timeout=timeout)
    except Exception as exc:
        print("connect failed: " + str(exc), file=sys.stderr)
        return 1

    try:
        for frame in encode_session(files):
            await transport.write_control(frame)
        # After the last COMMIT write, wait up to `timeout` for COMMITTED/NACK.
        try:
            await asyncio.wait_for(completed.wait(), timeout=timeout)
        except TimeoutError:
            print("timed out waiting for device COMMITTED", file=sys.stderr)
            return 1
    finally:
        try:
            await transport.disconnect()
        except Exception:
            pass

    return 1 if failed["flag"] else 0


def _default_device_name():
    """Read BLE_DEVICE_NAME from the embedded config without importing the device code."""
    try:
        from config import BLE_DEVICE_NAME  # type: ignore

        return BLE_DEVICE_NAME
    except Exception:
        return "snake-ota"


_NACK_NAMES = {
    0x01: "BAD_CRC",
    0x02: "BAD_PATH",
    0x03: "OVERSIZE",
    0x04: "OUT_OF_ORDER",
    0x05: "WRITE_FAILED",
    0x06: "PROTECTED",
}


def _nack_name(code):
    return _NACK_NAMES.get(code, "UNKNOWN")


class _BleakTransport:
    """Production transport using bleak. Imported lazily so tests don't need bleak."""

    def __init__(self):
        self._client = None
        self._status_cb = None

    async def connect(self, name, timeout):
        from bleak import BleakClient, BleakScanner  # type: ignore

        device = await BleakScanner.find_device_by_filter(lambda d, _adv: (d.name or "") == name, timeout=timeout)
        if device is None:
            raise RuntimeError("no device named " + repr(name) + " found within " + str(timeout) + "s")
        self._client = BleakClient(device)
        await self._client.connect()
        # Find our characteristics. UUIDs are stored as 128-bit bytes in ble_ota.py;
        # bleak expects UUID strings. We compare by exact bytes -> string conversion.
        self._control_uuid = _uuid_to_str(b"\x00\xff\x10\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        self._status_uuid = _uuid_to_str(b"\x00\xff\x10\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        await self._client.start_notify(self._status_uuid, self._notify)

    async def disconnect(self):
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass

    async def write_control(self, frame):
        if self._client is None:
            raise RuntimeError("transport not connected")
        await self._client.write_gatt_char(self._control_uuid, frame, response=False)

    def on_status(self, cb):
        self._status_cb = cb

    def _notify(self, _char, data):
        if self._status_cb is not None:
            self._status_cb(bytes(data))


def _uuid_to_str(b):
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


if __name__ == "__main__":
    sys.exit(main_sync(sys.argv[1:]))
