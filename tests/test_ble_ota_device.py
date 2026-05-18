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


def test_happy_path_writes_files_to_staging(chdir_tmp):
    files = [
        ("main.py", b"print('new')"),
        ("common/engine.py", b"# engine"),
    ]
    s = ble_ota.Session()
    statuses = feed(s, list(encode_session(files)))

    # Files should exist in .staging/ after END_FILE for each.
    for path, expected in files:
        staged = chdir_tmp / STAGING_DIR / path
        assert staged.exists(), "missing " + str(staged)
        assert staged.read_bytes() == expected

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
