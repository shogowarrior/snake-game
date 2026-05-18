"""Pure protocol-layer tests for BLE OTA. No BLE, no filesystem, no device wiring."""

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
