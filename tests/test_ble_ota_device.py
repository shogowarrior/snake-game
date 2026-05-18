"""Integration tests for the device-side BLE OTA wiring.

Tests do not use real BLE — they construct ble_ota.Session directly and feed it
frames byte-by-byte. The listen() driver gets tested separately once it exists.

Filesystem operations use tmp_path + chdir so staging writes are sandboxed.
"""

import ble_ota
import pytest
from ble_protocol import (
    NACK_BAD_CRC,
    NACK_BAD_PATH,
    NACK_OUT_OF_ORDER,
    NACK_PROTECTED,
    OP_ABORT,
    OP_BEGIN_FILE,
    OP_COMMITTED,
    OP_END_FILE,
    OP_FILE_CHUNK,
    OP_NACK,
    STAGING_DIR,
    compute_crc32,
    encode_begin_file,
    encode_frame,
    encode_session,
)


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def no_soft_reset(monkeypatch):
    """Replace machine.soft_reset with a recorded MagicMock so tests don't exit."""
    from unittest.mock import MagicMock

    import machine

    mock = MagicMock()
    monkeypatch.setattr(machine, "soft_reset", mock, raising=False)
    return mock


def feed(session, frames):
    """Push frames into a Session and collect status frames it produces."""
    statuses = []
    session.on_status = statuses.append
    for f in frames:
        session.handle_frame(f)
    return statuses


def test_session_starts_in_idle_state():
    s = ble_ota.Session()
    assert s.state == ble_ota.STATE_IDLE


def test_out_of_order_chunk_without_begin_nacks_and_aborts(chdir_tmp):
    s = ble_ota.Session()
    statuses = feed(s, [encode_frame(OP_FILE_CHUNK, 0, b"oops")])
    assert any(_decoded_op(st) == OP_NACK and _nack_reason(st) == NACK_OUT_OF_ORDER for st in statuses)
    assert s.state == ble_ota.STATE_ABORTED


def test_protected_path_in_begin_nacks_with_protected_reason(chdir_tmp):
    s = ble_ota.Session()
    # Construct the BEGIN_FILE payload manually — encode_begin_file would refuse
    # the protected name during validate_device_path. On the wire, the device's
    # parse_begin_file does the same check and raises ProtectedPath, which the
    # Session translates to NACK_PROTECTED.
    body = (10).to_bytes(4, "little") + (0).to_bytes(4, "little") + b"boot.py\x00"
    frame = encode_frame(OP_BEGIN_FILE, 0, body)
    statuses = feed(s, [frame])
    nacks = [st for st in statuses if _decoded_op(st) == OP_NACK]
    assert nacks, "expected a NACK status"
    assert _nack_reason(nacks[-1]) == NACK_PROTECTED
    assert s.state == ble_ota.STATE_ABORTED


def test_traversal_path_in_begin_nacks_with_bad_path_reason(chdir_tmp):
    """Distinct from the protected case — structural failures must give NACK_BAD_PATH."""
    s = ble_ota.Session()
    body = (10).to_bytes(4, "little") + (0).to_bytes(4, "little") + b"../etc/passwd\x00"
    frame = encode_frame(OP_BEGIN_FILE, 0, body)
    statuses = feed(s, [frame])
    nacks = [st for st in statuses if _decoded_op(st) == OP_NACK]
    assert nacks and _nack_reason(nacks[-1]) == NACK_BAD_PATH
    assert s.state == ble_ota.STATE_ABORTED


def _decoded_op(frame):
    return frame[0]


def _nack_reason(frame):
    # NACK payload is [seq, reason]
    return frame[5] if len(frame) >= 6 else None


def test_happy_path_writes_files_to_staging(chdir_tmp, no_soft_reset):
    files = [
        ("main.py", b"print('new')"),
        ("common/engine.py", b"# engine"),
    ]
    s = ble_ota.Session()
    statuses = feed(s, list(encode_session(files)))

    # After commit, files live at the device root (== tmp_path); .staging is wiped.
    for path, expected in files:
        assert (chdir_tmp / path).read_bytes() == expected

    # State should have walked all the way to COMMITTED.
    assert s.state == ble_ota.STATE_COMMITTED
    # Every chunk acked, no NACKs.
    nacks = [st for st in statuses if st[0] == OP_NACK]
    assert nacks == []


def test_bad_crc_nacks_and_no_file_appears(chdir_tmp):
    # Build frames where END_FILE's expected CRC doesn't match the body.
    body = b"abc"
    bad_crc = (compute_crc32(body) + 1) & 0xFFFFFFFF
    begin_payload = encode_begin_file("main.py", len(body), bad_crc)
    frames = [
        encode_frame(OP_BEGIN_FILE, 0, begin_payload),
        encode_frame(OP_FILE_CHUNK, 1, body),
        encode_frame(OP_END_FILE, 2, b""),
    ]
    s = ble_ota.Session()
    statuses = feed(s, frames)
    assert any(st[0] == OP_NACK and st[5] == NACK_BAD_CRC for st in statuses)
    assert s.state == ble_ota.STATE_ABORTED
    # Partial-write to .staging/main.py is cleaned up.
    staged = chdir_tmp / STAGING_DIR / "main.py"
    assert not staged.exists()


def test_staging_dir_is_cleaned_on_abort(chdir_tmp):
    body = b"hi"
    frames = [
        encode_frame(OP_BEGIN_FILE, 0, encode_begin_file("main.py", len(body), compute_crc32(body))),
        encode_frame(OP_FILE_CHUNK, 1, body),
        encode_frame(OP_END_FILE, 2, b""),
        encode_frame(OP_ABORT, 3, b""),
    ]
    s = ble_ota.Session()
    feed(s, frames)
    assert s.state == ble_ota.STATE_ABORTED
    # Staging dir should be wiped on abort.
    assert not (chdir_tmp / STAGING_DIR).exists()


def test_commit_renames_staging_files_into_place(chdir_tmp, no_soft_reset):
    files = [
        ("main.py", b"print('new')"),
        ("common/engine.py", b"# new engine"),
    ]
    s = ble_ota.Session()
    feed(s, list(encode_session(files)))
    # After commit, files live at the device root (== tmp_path), not in .staging.
    for path, expected in files:
        assert (chdir_tmp / path).read_bytes() == expected
    assert not (chdir_tmp / STAGING_DIR).exists()
    assert s.state == ble_ota.STATE_COMMITTED
    no_soft_reset.assert_called_once()


def test_manifest_deletes_files_not_in_manifest(chdir_tmp, no_soft_reset):
    # Pre-existing files in scope, only one of which is in the new manifest.
    (chdir_tmp / "common").mkdir()
    (chdir_tmp / "common" / "old.py").write_text("# stale")
    (chdir_tmp / "common" / "engine.py").write_text("# old engine")
    (chdir_tmp / "main.py").write_text("# old main")

    files = [
        ("main.py", b"# new main"),
        ("common/engine.py", b"# new engine"),
    ]
    s = ble_ota.Session()
    feed(s, list(encode_session(files)))

    assert (chdir_tmp / "main.py").read_bytes() == b"# new main"
    assert (chdir_tmp / "common" / "engine.py").read_bytes() == b"# new engine"
    assert not (chdir_tmp / "common" / "old.py").exists()


def test_protected_files_never_deleted_by_commit(chdir_tmp, no_soft_reset):
    # high_score.txt sits at root and is not in any manifest. It must survive.
    (chdir_tmp / "high_score.txt").write_text("42")

    files = [("main.py", b"# new")]
    s = ble_ota.Session()
    feed(s, list(encode_session(files)))

    assert (chdir_tmp / "high_score.txt").read_text() == "42"


def test_commit_emits_committed_status(chdir_tmp, no_soft_reset):
    files = [("main.py", b"x")]
    s = ble_ota.Session()
    statuses = feed(s, list(encode_session(files)))
    assert any(st[0] == OP_COMMITTED for st in statuses)


def test_commit_pass_handles_empty_manifest(chdir_tmp, no_soft_reset):
    # MANIFEST with no paths after zero files. Edge case: no files transferred,
    # client sends empty manifest + COMMIT (clears everything in allowlist).
    (chdir_tmp / "main.py").write_text("# old")
    frames = list(encode_session([]))
    s = ble_ota.Session()
    feed(s, frames)
    assert not (chdir_tmp / "main.py").exists()
    assert s.state == ble_ota.STATE_COMMITTED


def test_listen_returns_after_timeout_with_no_client(chdir_tmp, no_soft_reset, monkeypatch):
    """If no central connects in `timeout_secs`, listen() returns falsy and never resets."""
    # Use a tiny timeout to keep the test fast.
    result = ble_ota.listen(timeout_secs=0.05)
    assert result is False
    no_soft_reset.assert_not_called()


def test_listen_drives_session_when_client_writes_frames(chdir_tmp, no_soft_reset, monkeypatch):
    """End-to-end: connect, send a full session, expect commit + soft_reset."""
    files = [("main.py", b"print('ota')")]
    frames = list(encode_session(files))

    # Install a fake BLE that auto-connects and pumps frames inside listen().
    import bluetooth

    bt = bluetooth.BLE()

    def auto_session(control_handle):
        bt.client_connect()
        for f in frames:
            bt.client_write(control_handle, f)

    # listen() is expected to expose its control characteristic handle so a
    # test driver can poke writes. Hook via a module-level injection.
    monkeypatch.setattr(ble_ota, "_on_listen_ready", lambda control_handle, status_handle: auto_session(control_handle))

    ble_ota.listen(timeout_secs=2.0, ble=bt)

    # Files were committed and soft_reset was called.
    assert (chdir_tmp / "main.py").read_bytes() == b"print('ota')"
    no_soft_reset.assert_called_once()


def test_listen_lights_corner_pixel_while_advertising(chdir_tmp, no_soft_reset, monkeypatch):
    """The visual indicator must call display.set_pixel + flush at least once."""
    calls = []
    import display

    monkeypatch.setattr(display, "set_pixel", lambda x, y, c: calls.append(("set", x, y, c)))
    monkeypatch.setattr(display, "flush", lambda: calls.append(("flush",)))

    ble_ota.listen(timeout_secs=0.05)
    assert any(c[0] == "set" for c in calls)
    assert any(c[0] == "flush" for c in calls)


def test_main_run_game_skips_listen_when_flag_disabled(monkeypatch):
    """When BLE_OTA_ENABLED=False, main.run_game must not import ble_ota."""
    import sys

    monkeypatch.delitem(sys.modules, "ble_ota", raising=False)

    import config

    monkeypatch.setattr(config, "BLE_OTA_ENABLED", False)

    # Stub SnakeGame so run_game's loop exits immediately.
    import game

    class _OneShotGame:
        def __init__(self, *a, **kw):
            self.engine = type("E", (), {"game_over": True})()

        def start_game(self):
            pass

        def tick(self):
            pass

        def end_game(self):
            raise KeyboardInterrupt  # exit run_game cleanly

    monkeypatch.setattr(game, "SnakeGame", _OneShotGame)

    import main

    try:
        main.run_game()
    except KeyboardInterrupt:
        pass
    assert "ble_ota" not in sys.modules
