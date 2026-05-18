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


async def _push_async(files, name, timeout):
    # Real bleak wiring lives in Task 14; for now this path is unused under dry-run.
    raise NotImplementedError("BLE push runtime is added in Task 14")


if __name__ == "__main__":
    sys.exit(main_sync(sys.argv[1:]))
