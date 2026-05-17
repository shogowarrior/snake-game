# BLE OTA for the embedded snake build — design

**Status:** draft
**Date:** 2026-05-17
**Branch:** `bluetooth`

## Problem

The embedded build is flashed today by [`.claude/skills/flash-snake`](../../../.claude/skills/flash-snake/SKILL.md), which wraps `mpremote cp` over USB. Every iteration cycle needs the device on the desk and tethered to a serial cable. We want to push updated Python over Bluetooth Low Energy instead: scan, connect, transfer, soft-reset, done — no cable.

Scope is **app-level file sync**: `src/embedded/*.py` and `src/common/**/*.py`. Not partition-level firmware OTA — MicroPython itself, the bootloader, and `boot.py` are out of scope.

The current `mpremote` workflow stays as the canonical "device is bricked, fall back to USB" path. BLE OTA layers on top.

## Decisions

These are the design choices reached in [brainstorming](#references). Listed up front so the rest of this doc reads as elaboration, not exploration.

1. **Boot-window listen.** Device advertises BLE for ~3s on every boot. If a central connects, complete the transfer; otherwise, skip BLE entirely and start the game. No BLE concurrent with gameplay.
2. **Simple framed protocol** over a single GATT service. One file at a time. Opcode + seq + payload-length header.
3. **Full sync with staging.** Files written to `/.staging/<path>`; only after a final `COMMIT` opcode are they renamed into place atomically. A failed transfer leaves the old files intact.
4. **Manifest-driven deletion.** Client sends the canonical file list before `COMMIT`; commit-pass deletes anything in the synced dirs not in the manifest.
5. **Master kill-switch.** `BLE_OTA_ENABLED` in `config.py`. When `False`, no BLE stack is imported.
6. **Python CLI + thin skill.** `tools/ble_push.py` on the host, plus a `.claude/skills/ble-push-snake/` wrapper.
7. **No authentication.** Open service. Documented as a deliberate non-goal; revisit if the threat model changes.
8. **Testable without hardware.** Pure protocol unit tests + `sim/fake_bluetooth.py` integration shim, in the same pattern as `fake_machine`/`fake_neopixel`.

## Architecture

```text
src/embedded/
  ble_ota.py         # GATT server, listen window, frame parser, staging + commit
  config.py          # + BLE_OTA_ENABLED, BLE_LISTEN_SECONDS, BLE_DEVICE_NAME
  main.py            # modified: optional listen window before run_game()

src/sim/
  fake_bluetooth.py  # in-memory BLE shim that parallels fake_machine/fake_neopixel

scripts/
  ble_push.py        # bleak-based CLI: scans, connects, frames+sends files

.claude/skills/
  ble-push-snake/    # thin skill wrapping `uv run python scripts/ble_push.py`

tests/
  test_ble_protocol.py     # pure: frame encode/decode, CRC, manifest parser
  test_ble_ota_device.py   # integration: drives ble_ota via fake_bluetooth
  test_ble_push_client.py  # host: encoder + bleak substitute
```

Three layers, each independently testable:

- **Protocol layer** (`ble_ota.py` encoder/decoder, mirrored on the client) — pure functions on bytes. No BLE, no filesystem.
- **Device wiring** (`ble_ota.listen()`) — owns the GATT server, drives the parser, owns the staging dir and commit pass.
- **Host CLI** (`tools/ble_push.py`) — owns scan, connect, file walking, async write loop.

The protocol layer is the seam. Encoder and decoder are shared code (same module, used from both target shapes), so a round-trip is byte-for-byte symmetric.

## Wire protocol

One GATT service. Concrete UUIDs settled at implementation time; the service exposes:

- **`CONTROL`** — `WRITE_NO_RESPONSE`. Client → device. All frames flow here.
- **`STATUS`** — `NOTIFY`. Device → client. Acks and errors.

### Frame format (CONTROL)

```text
[ 1 byte opcode ][ 1 byte seq ][ 2 bytes payload_len LE ][ payload... ]
```

`seq` wraps mod 256, lets the device detect drops/duplicates. `payload_len` is bounded by `negotiated_MTU - 4`. ESP32 MicroPython typically negotiates 240–500 bytes.

### Opcodes (client → device)

| Op | Name | Payload | Meaning |
| --- | --- | --- | --- |
| `0x01` | `BEGIN_FILE` | `<u32 size><u32 crc32><path\0>` | Start of a file. `path` is null-terminated UTF-8, device-relative (`common/engine.py`, `main.py`, ...). |
| `0x02` | `FILE_CHUNK` | raw bytes | Body bytes for the current file. Multiple per file. |
| `0x03` | `END_FILE` | (empty) | Body done. Device verifies CRC against `BEGIN_FILE`'s declared value. |
| `0x04` | `MANIFEST` | `<path1>\n<path2>\n...` | Sent last, after all files. The canonical file set for deletion-pass. |
| `0x05` | `COMMIT` | (empty) | Run commit pass, send `COMMITTED`, soft-reset. |
| `0x06` | `ABORT` | (empty) | Client gives up. Device wipes `/.staging/`, returns to game. |

### Status (device → client)

| Op | Name | Payload | When |
| --- | --- | --- | --- |
| `0x81` | `ACK` | `<seq>` | Frame accepted. |
| `0x82` | `NACK` | `<seq><u8 reason>` | Bad CRC, out-of-order opcode, write failure, oversize, invalid path. |
| `0x83` | `READY` | (empty) | Sent once on connect. "I'm in OTA mode, send frames." |
| `0x84` | `COMMITTED` | (empty) | Commit succeeded, soft-reset imminent. |

### Bounds

Bake-in constants in `ble_ota.py`:

- `MAX_PATH_LEN = 64` — bytes, including null terminator.
- `MAX_FILE_SIZE = 16384` — per-file byte cap. Generous for any `.py` in this repo.
- `MAX_FRAMES_PER_SESSION = 4096` — DoS guard.

Any `BEGIN_FILE` violating these → immediate `NACK` and session abort.

### Failure semantics

- Any `NACK` from device → client decides retry/abort.
- BLE disconnect mid-transfer → device wipes `/.staging/` and soft-resets back into the game with the **old** files intact. This is the whole point of staging.
- Out-of-order opcode (e.g. `FILE_CHUNK` before `BEGIN_FILE`) → `NACK` and abort.
- Path containing `..`, leading `/`, or escaping the synced-dirs allowlist → `NACK` and abort.

## Device-side state machine

`ble_ota.listen(display, timeout_secs)` runs at boot before `run_game()`. Returns when the listen window closes, the client aborts, or BLE disconnects. Returns nothing useful on commit — the device has soft-reset by then.

```text
       BLE_OTA_ENABLED=False ──────────────────────────────────► skip, run game
                                  ▲
                                  │
[boot] ── show_listen_indicator() ┴─► state=ADVERTISING ──── timeout (3s) ────► run game
                                       │
                                       │ central connects
                                       ▼
                                  state=CONNECTED ── send READY ──┐
                                       │                          │
                                       │ BEGIN_FILE                ▼
                                       ▼                  ┌───────────────┐
                                  state=RECEIVING ◄───────┤ FILE_CHUNK    │
                                       │                  └───────────────┘
                                       │ END_FILE (crc ok) ──► state=IDLE_BETWEEN_FILES
                                       │
                                       │ MANIFEST ──► state=AWAITING_COMMIT
                                       │
                                       │ COMMIT ──► commit pass + soft_reset
                                       │
                                       │ ABORT / disconnect / timeout / NACK-fail
                                       ▼
                                  cleanup_staging() ──► run game
```

### Commit pass

```text
1. For each path in manifest:
       if /.staging/<path> exists:
           os.rename("/.staging/" + path, "/" + path)
2. For each existing file under the synced-dirs allowlist:
       if path in PROTECTED_FILES:    continue   # never delete /boot.py et al.
       if path in manifest:           continue
       os.remove(path)
3. Recursively remove /.staging/.
4. gatts_notify(COMMITTED).
5. machine.soft_reset()
```

`BEGIN_FILE` with a path matching `PROTECTED_FILES` is rejected at parse time
(`NACK` + abort) — protected files can never enter `/.staging/` in the first place.

### Synced-dirs allowlist

Hard-coded in `ble_ota.py`, **not** in `config.py`:

```python
SYNCED_DIRS = ("/common/",)
SYNCED_TOP_LEVEL_GLOBS = ("*.py",)
PROTECTED_FILES = ("/boot.py", "/high_score.txt", "/secrets.py")
```

The commit pass never touches anything outside the allowlist, and never deletes anything in `PROTECTED_FILES` even if it's outside the manifest. `/boot.py` is excluded because we want USB recovery to keep working; `/high_score.txt` persists across reflashes by design; `/secrets.py` is reserved if anyone re-enables wifi later.

### Visual indicator

`listen()` borrows the `Display` reference from `main.py` and writes a single pixel:

- **Blue** corner pixel: advertising.
- **Cyan** corner pixel: client connected, transfer in progress.
- **Off** when `listen()` returns or the device soft-resets.

Reuses `display.set_pixel` + `display.flush` — no new rendering path.

## Configuration

In [src/embedded/config.py](../../src/embedded/config.py):

```python
# --- BLE OTA --------------------------------------------------------
# Master switch. False = main.py boots straight into the game; no BLE
# stack is initialized, no flash spent on listen.
BLE_OTA_ENABLED = True

# Seconds to advertise before falling through to the game. Keep short
# so the device isn't unresponsive after a power cycle.
BLE_LISTEN_SECONDS = 3

# Name the device advertises. Visible from the host's BLE scanner;
# the host CLI matches on this exact string by default.
BLE_DEVICE_NAME = "snake-ota"
```

[src/embedded/main.py](../../src/embedded/main.py) gains a lazy import + listen call:

```python
from config import BLE_OTA_ENABLED, BLE_LISTEN_SECONDS
from display import Display
from game import SnakeGame


def run_game():
    display = Display()
    if BLE_OTA_ENABLED:
        from ble_ota import listen
        listen(display, BLE_LISTEN_SECONDS)
    while True:
        game = SnakeGame(display, policy_name=POLICY)
        game.start_game()
        while not game.engine.game_over:
            game.tick()
        game.end_game()
```

Lazy import is intentional. When `BLE_OTA_ENABLED=False`, `ble_ota` is never loaded and the `bluetooth` module's RAM cost is skipped entirely.

## Host CLI

[scripts/ble_push.py](../../scripts/ble_push.py) is a standalone module, in the same spot as the existing `scripts/preview_score.py`. Dependency: `bleak` (cross-platform BLE), added as a dev/optional dependency in `pyproject.toml` so the desktop training target doesn't pull it.

### Surface

```bash
uv run python scripts/ble_push.py                          # full sync, defaults
uv run python scripts/ble_push.py --name snake-ota         # match different advertised name
uv run python scripts/ble_push.py --dry-run                # encode locally, don't connect
uv run python scripts/ble_push.py --timeout 20             # scan timeout (default 10s)
```

### Internal structure

```python
def collect_files(repo_root: Path) -> list[tuple[str, bytes]]:
    # Walk src/embedded/*.py and src/common/**/*.py → [(device_path, bytes)]
    # device_path is what the device sees: "main.py", "common/engine.py"

def encode_session(files: list[tuple[str, bytes]]) -> Iterator[bytes]:
    # Yields frames: BEGIN_FILE, FILE_CHUNK*, END_FILE, ... MANIFEST, COMMIT
    # Pure function. Same code path the device decoder consumes.

async def push(files, device_name: str, scan_timeout: float):
    # bleak: scan for device_name, connect, find CONTROL/STATUS chars,
    # drain encode_session() into CONTROL writes, await STATUS notifies,
    # fail loudly on NACK or timeout.
```

`encode_session` is the seam: it's pure bytes-in/bytes-out, exercised both by host-side unit tests and the device integration tests.

### `ble-push-snake` skill

A new skill at `.claude/skills/ble-push-snake/SKILL.md`, parallel to `flash-snake`. One-line recipe (`uv run python scripts/ble_push.py`) plus a debugging section covering the common failure modes:

- Device not found by scan → check `BLE_OTA_ENABLED`, check you're inside the boot window, check the advertised name.
- Connection drops mid-transfer → device falls back to old files; safe to retry.
- `NACK` codes → table of meanings.

## Testing

Three test files, mapping to the three architectural layers.

### `tests/test_ble_protocol.py` — pure, fast

Targets the encoder/decoder and manifest parser. No device code, no BLE, no filesystem.

Coverage:

- Frame encode → decode round-trip for every opcode.
- Oversize payload → `FrameTooLarge`.
- Path validation rejects `..`, absolute paths, overlength names.
- `encode_session` emits opcodes in the correct order: `BEGIN/CHUNK*/END` per file, then `MANIFEST`, then `COMMIT`.
- CRC computation matches `binascii.crc32`.

These run in milliseconds and catch ~80% of bug surface.

### `tests/test_ble_ota_device.py` — integration via `fake_bluetooth`

Drives `ble_ota.listen()` against an in-memory fake. Each test:

1. Sets up a tmp filesystem root so staging writes go to `tmp_path/.staging/`, not `/.staging/`.
2. Wires `fake_bluetooth` so writes to the fake `CONTROL` characteristic invoke the device's IRQ handler.
3. Plays a frame script — same frames `encode_session` would produce.
4. Asserts: files at expected paths, removed files gone, `COMMITTED` sent, `machine.soft_reset` called.

Cases:

- **Happy path** — files committed, manifest-driven deletion works, `/.staging/` cleaned, `soft_reset` called.
- **Mid-transfer disconnect** — `/.staging/` cleaned, original files intact, no `soft_reset`.
- **Bad CRC** — `NACK` sent, session aborts, no files written.
- **Client `ABORT`** — `/.staging/` cleaned, no `soft_reset`.
- **Path traversal in `BEGIN_FILE`** — `NACK` and abort.
- **Listen window timeout** (no client) — `listen()` returns, no `soft_reset`.
- **Protected file in manifest** — `NACK` and abort (can't OTA `boot.py`).

### `tests/test_ble_push_client.py` — host side

Same `encode_session` exercised from the client's perspective, plus a small `bleak`-substitute fake for `push()`. Verifies:

- Client sends frames in correct order.
- Client surfaces a clear, structured error on `NACK` (current spec is fail-fast — no retries).
- Client surfaces clear errors on disconnect mid-transfer.

### `sim/fake_bluetooth.py` shim

In the same pattern as `fake_neopixel.py`: minimal surface area matching the real `bluetooth.BLE` interface, plus a test-only API to drive it.

```python
class BLE:
    def __init__(self):
        self._chars = {}
        self._notify_subs = []
        self._irq = None

    def active(self, on=True): pass
    def config(self, **kw): pass

    def gatts_register_services(self, services):
        ...  # allocate handles, return tuple-of-tuples

    def gatts_write(self, handle, data):
        self._chars[handle] = data

    def gatts_notify(self, conn_handle, value_handle, data):
        for cb in self._notify_subs: cb(value_handle, data)

    def irq(self, handler):
        self._irq = handler

    # Test-only API (not on real bluetooth.BLE):
    def client_write(self, char_uuid, data): ...
    def client_connect(self): ...
    def client_disconnect(self): ...
```

`tests/conftest.py` extends as one line:

```python
sys.modules["bluetooth"] = fake_bluetooth.BluetoothModule()
```

A `fake_machine_reset` fixture monkey-patches `machine.soft_reset` to a `MagicMock` so tests can assert the reboot would have happened without actually exiting the test process.

## Failure modes and recovery

- **OTA bricks the app code.** Staging guarantees the old files survive any failure before `COMMIT`. The only window where a partial state is possible is between rename calls in step 1 of the commit pass — if power dies there, some new files and some old files coexist. Acceptable: USB recovery via `flash-snake` is the documented fallback.
- **OTA bricks `boot.py`.** Can't happen — `boot.py` is in `PROTECTED_FILES`.
- **OTA bricks `main.py`.** Possible if a syntactically-invalid `main.py` is pushed. Device boots, fails import, drops to REPL. USB recovery via `flash-snake`.
- **`BLE_OTA_ENABLED=True` causes ESP32 boot failure** (e.g. bluetooth module unavailable on a board variant). User flips it back to `False` via USB. Adding a safety net (boot button held → skip OTA) is out of scope; one config-flip via USB is acceptable.
- **Disconnect during commit pass.** Device finishes the pass anyway — the client doesn't drive it.

## Non-goals

- **Firmware OTA.** Updating MicroPython itself or the bootloader is out of scope; `boot.py` is protected.
- **Authentication / pairing.** Threat model doesn't justify the complexity of MicroPython's BLE bonding. Revisit if the device leaves a private network.
- **Concurrent BLE + gameplay.** Boot-window listen by design. The game never has to share a CPU with the BLE stack.
- **Hash-based diff sync.** Full sync is fast enough at our file sizes; device-side hashing isn't worth the RAM.
- **Progress UI during transfer.** A static blue/cyan corner pixel is enough; the listen window is short.
- **Resumable transfers.** If a session fails, the client re-runs from scratch.

## Open questions

None at this design phase. UUIDs and concrete `NACK` reason codes are deferred to implementation.

## References

- [src/embedded/config.py](../../src/embedded/config.py) — existing config knobs the new flags slot into.
- [src/embedded/wlan.py](../../src/embedded/wlan.py) — prior networking precedent (commented-out WiFi/webrepl).
- [.claude/skills/flash-snake/SKILL.md](../../.claude/skills/flash-snake/SKILL.md) — USB flash recipe; BLE-push skill mirrors its shape.
- [src/sim/fake_machine.py](../../src/sim/fake_machine.py), [src/sim/fake_neopixel.py](../../src/sim/fake_neopixel.py) — the pattern `fake_bluetooth.py` follows.
- [tests/conftest.py](../../tests/conftest.py) — where the new `sys.modules["bluetooth"]` shim plugs in.
