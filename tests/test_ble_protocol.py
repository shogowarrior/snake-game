"""Pure protocol-layer tests for BLE OTA. No BLE, no filesystem, no device wiring."""

import pytest
from ble_protocol import (
    MAX_FILE_SIZE,
    MAX_FRAMES_PER_SESSION,
    MAX_PATH_LEN,
    NACK_BAD_CRC,
    NACK_BAD_PATH,
    NACK_OUT_OF_ORDER,
    NACK_OVERSIZE,
    NACK_PROTECTED,
    NACK_WRITE_FAILED,
    OP_ABORT,
    OP_ACK,
    OP_BEGIN_FILE,
    OP_COMMIT,
    OP_COMMITTED,
    OP_END_FILE,
    OP_FILE_CHUNK,
    OP_MANIFEST,
    OP_NACK,
    OP_READY,
    PROTECTED_FILES,
    SYNCED_DIRS,
    SYNCED_TOP_LEVEL_GLOBS,
    BadCRC,
    FrameTooLarge,
    InvalidFrame,
    InvalidPath,
    ProtectedPath,
    decode_frame,
    encode_frame,
    validate_device_path,
)


def test_opcode_values_are_stable():
    # Wire-protocol values; changing these breaks compatibility with deployed devices.
    assert OP_BEGIN_FILE == 0x01
    assert OP_FILE_CHUNK == 0x02
    assert OP_END_FILE == 0x03
    assert OP_MANIFEST == 0x04
    assert OP_COMMIT == 0x05
    assert OP_ABORT == 0x06
    assert OP_ACK == 0x81
    assert OP_NACK == 0x82
    assert OP_READY == 0x83
    assert OP_COMMITTED == 0x84


def test_bounds_constants():
    assert MAX_PATH_LEN == 64
    assert MAX_FILE_SIZE == 16384
    assert MAX_FRAMES_PER_SESSION == 4096


def test_synced_dirs_and_protected_files():
    assert SYNCED_DIRS == ("common",)
    assert SYNCED_TOP_LEVEL_GLOBS == ("*.py",)
    assert PROTECTED_FILES == ("boot.py", "high_score.txt", "secrets.py")


def test_nack_reasons_are_distinct():
    reasons = {NACK_BAD_CRC, NACK_BAD_PATH, NACK_OVERSIZE, NACK_OUT_OF_ORDER, NACK_WRITE_FAILED, NACK_PROTECTED}
    assert len(reasons) == 6


def test_exceptions_are_distinct_classes():
    assert issubclass(FrameTooLarge, Exception)
    assert issubclass(InvalidPath, Exception)
    assert issubclass(ProtectedPath, InvalidPath)  # subclass — code can catch broad InvalidPath
    assert issubclass(InvalidFrame, Exception)
    assert issubclass(BadCRC, Exception)


def test_frame_round_trip_empty_payload():
    frame = encode_frame(OP_COMMIT, seq=42, payload=b"")
    op, seq, payload = decode_frame(frame)
    assert op == OP_COMMIT
    assert seq == 42
    assert payload == b""


def test_frame_round_trip_with_payload():
    frame = encode_frame(OP_FILE_CHUNK, seq=7, payload=b"hello world")
    op, seq, payload = decode_frame(frame)
    assert (op, seq, payload) == (OP_FILE_CHUNK, 7, b"hello world")


def test_frame_seq_wraps_at_256():
    # seq is one byte; encoder accepts 0..255 only
    frame = encode_frame(OP_FILE_CHUNK, seq=255, payload=b"x")
    _, seq, _ = decode_frame(frame)
    assert seq == 255

    with pytest.raises(ValueError):
        encode_frame(OP_FILE_CHUNK, seq=256, payload=b"x")
    with pytest.raises(ValueError):
        encode_frame(OP_FILE_CHUNK, seq=-1, payload=b"x")


def test_oversize_payload_rejected_on_encode():
    with pytest.raises(FrameTooLarge):
        encode_frame(OP_FILE_CHUNK, seq=0, payload=b"x" * 10_000)


def test_decode_rejects_truncated_header():
    with pytest.raises(InvalidFrame):
        decode_frame(b"\x01\x00")  # only 2 bytes — header is 4


def test_decode_rejects_payload_shorter_than_declared():
    # opcode=0x02, seq=0, payload_len=10 LE, body=only 3 bytes
    bad = bytes([0x02, 0x00, 0x0A, 0x00]) + b"abc"
    with pytest.raises(InvalidFrame):
        decode_frame(bad)


def test_decode_rejects_unknown_opcode():
    # encoder uses 0xFF which isn't a defined opcode; decoder should refuse
    bad = bytes([0xFF, 0x00, 0x00, 0x00])
    with pytest.raises(InvalidFrame):
        decode_frame(bad)


@pytest.mark.parametrize(
    "path",
    [
        "main.py",
        "common/engine.py",
        "common/colors.py",
        "display.py",
    ],
)
def test_validate_accepts_legal_paths(path):
    validate_device_path(path)  # should not raise


@pytest.mark.parametrize(
    "path",
    [
        "",  # empty
        "/main.py",  # absolute
        "../etc/passwd",  # traversal
        "common/../boot.py",  # traversal via subdir
        "common/./engine.py",  # current-dir segment (suspicious; reject)
        "x" * 65,  # over MAX_PATH_LEN (including null we add)
        "foo\x00bar.py",  # embedded null
        "subdir/foo.py",  # not in SYNCED_DIRS allowlist
        "common/nested/deep.py",  # more than one level under common (out of scope)
        "main.txt",  # top-level non-.py
        "common/foo",  # no extension in common/ — reject (we sync .py only)
    ],
)
def test_validate_rejects_illegal_paths(path):
    with pytest.raises(InvalidPath):
        validate_device_path(path)


@pytest.mark.parametrize("path", ["boot.py", "high_score.txt", "secrets.py"])
def test_validate_rejects_protected_files(path):
    with pytest.raises(InvalidPath):
        validate_device_path(path)
