---
name: ble-push-snake
description: Use when the user asks to push the embedded snake build to the ESP32 over Bluetooth instead of USB. Wraps `scripts/ble_push.py` (BLE OTA) with the paths this repo's `src/common/` + `src/embedded/` layout expects. Trigger even when the user just says "ota it", "push over bluetooth", "send to the matrix wirelessly".
---

# Push snake to ESP32 over BLE

The embedded build accepts over-the-air updates over Bluetooth Low Energy when
`BLE_OTA_ENABLED = True` (the default) in `src/embedded/config.py`. On every
boot the device advertises as `"snake-ota"` for ~3 seconds; if a client
connects, the new files transfer, the device soft-resets, and the game starts
with the new code.

If BLE is unavailable, fall back to the `flash-snake` skill (USB).

## Recipe

From the repo root, power-cycle the device, then within ~3 seconds run:

```bash
uv run python scripts/ble_push.py
```

You should see:

```text
device: READY
device: COMMITTED
```

After `COMMITTED` the device soft-resets and the matrix starts drawing within
~1 second.

## Options

- `--name <str>` — advertised name to scan for (default reads `BLE_DEVICE_NAME` from `src/embedded/config.py`).
- `--dry-run` — encode and print frames without connecting. Useful for sanity-checking what would be sent.
- `--timeout <secs>` — scan/connect timeout (default 10s). Increase if the device boot window is missed.

## Debugging

**No device found.** The boot window is short. Power-cycle the device and run the push within ~3s. If you missed the window, just power-cycle again. To confirm the device is advertising, run `bluetoothctl scan on` (Linux) or use any BLE scanner app — it should appear as `snake-ota`.

**`BLE_OTA_ENABLED = False` was set.** OTA is disabled. Re-enable via USB:

```bash
mpremote connect /dev/ttyUSB0 exec "import config; print(config.BLE_OTA_ENABLED)"
```

Edit `src/embedded/config.py`, re-flash via `flash-snake`, then OTA going forward.

**`device: NACK reason=0x01 (BAD_CRC)`.** Transient corruption on the BLE link. Retry.

**`device: NACK reason=0x02 (BAD_PATH)`.** A file in your local tree has a path the device refuses. Check `validate_device_path` in `src/embedded/ble_protocol.py` — the allowlist is `src/embedded/*.py` + `src/common/*.py`, and anything outside is rejected.

**`device: NACK reason=0x06 (PROTECTED)`.** The push tried to overwrite a protected file (`boot.py`, `high_score.txt`, `secrets.py`). These are never OTA-updatable by design; re-flash over USB if you need to change them.

**Device hangs after push.** A syntactically-invalid `main.py` was pushed. Recover via USB: `flash-snake` from the last known good commit. The high score on the device is preserved.

## What this skill does NOT do

- Update MicroPython itself or `boot.py`. Use `mpremote` for those.
- Run lint or tests before pushing. Run `uv run ruff check src/` and `uv run pytest` separately if you want a gate.
- Pair/bond with the device. The BLE service is unauthenticated. Fine for a private workspace; revisit if the device leaves your network.
