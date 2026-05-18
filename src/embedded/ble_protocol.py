"""Pure protocol layer for BLE OTA. MicroPython-safe: no typing, no dataclasses,
no f-strings beyond basic interpolation. Imported by both src/embedded/ble_ota.py
(device wiring) and scripts/ble_push.py (host CLI).
"""

# ---- Opcodes (client -> device) -----------------------------------
OP_BEGIN_FILE = 0x01
OP_FILE_CHUNK = 0x02
OP_END_FILE = 0x03
OP_MANIFEST = 0x04
OP_COMMIT = 0x05
OP_ABORT = 0x06

# ---- Opcodes (device -> client, sent over STATUS notify) ----------
OP_ACK = 0x81
OP_NACK = 0x82
OP_READY = 0x83
OP_COMMITTED = 0x84

# ---- NACK reason codes --------------------------------------------
NACK_BAD_CRC = 0x01
NACK_BAD_PATH = 0x02
NACK_OVERSIZE = 0x03
NACK_OUT_OF_ORDER = 0x04
NACK_WRITE_FAILED = 0x05
NACK_PROTECTED = 0x06

# ---- Wire bounds --------------------------------------------------
MAX_PATH_LEN = 64
MAX_FILE_SIZE = 16384
MAX_FRAMES_PER_SESSION = 4096
MAX_PAYLOAD_LEN = 512  # frame payload cap; fits any plausible negotiated MTU

# ---- Filesystem allowlist (relative paths; device root = "/") -----
SYNCED_DIRS = ("common",)
SYNCED_TOP_LEVEL_GLOBS = ("*.py",)
PROTECTED_FILES = ("boot.py", "high_score.txt", "secrets.py")

# ---- Staging directory --------------------------------------------
STAGING_DIR = ".staging"


# ---- Exceptions ---------------------------------------------------
class FrameTooLarge(Exception):
    """Payload exceeds MAX_PAYLOAD_LEN."""


class InvalidPath(Exception):
    """Path fails structural validation: traversal, absolute, overlength, allowlist miss."""


class ProtectedPath(InvalidPath):
    """Path is structurally valid but matches PROTECTED_FILES (boot.py, high_score.txt, ...).

    Subclass of InvalidPath so callers that only care about "path rejected" still work.
    The device-side handler catches this specifically to emit NACK_PROTECTED rather than
    the more generic NACK_BAD_PATH.
    """


class InvalidFrame(Exception):
    """Frame header is malformed or truncated."""


class BadCRC(Exception):
    """END_FILE arrived but computed CRC doesn't match BEGIN_FILE's declared value."""


# ---- Frame codec --------------------------------------------------
# Wire format: [1 byte op][1 byte seq][2 bytes payload_len LE][payload]

_HEADER_LEN = 4
_KNOWN_OPS = frozenset(
    (
        OP_BEGIN_FILE,
        OP_FILE_CHUNK,
        OP_END_FILE,
        OP_MANIFEST,
        OP_COMMIT,
        OP_ABORT,
        OP_ACK,
        OP_NACK,
        OP_READY,
        OP_COMMITTED,
    )
)


def encode_frame(op, seq, payload):
    """Encode one frame to bytes. Raises ValueError on bad seq, FrameTooLarge on oversize."""
    if not (0 <= seq <= 255):
        raise ValueError("seq must be 0..255, got " + repr(seq))
    n = len(payload)
    if n > MAX_PAYLOAD_LEN:
        raise FrameTooLarge("payload " + str(n) + " > MAX_PAYLOAD_LEN " + str(MAX_PAYLOAD_LEN))
    return bytes([op & 0xFF, seq & 0xFF, n & 0xFF, (n >> 8) & 0xFF]) + bytes(payload)


def decode_frame(buf):
    """Decode one frame from bytes -> (op, seq, payload). Raises InvalidFrame on malformed input."""
    if len(buf) < _HEADER_LEN:
        raise InvalidFrame("truncated header (got " + str(len(buf)) + " bytes)")
    op = buf[0]
    seq = buf[1]
    payload_len = buf[2] | (buf[3] << 8)
    if op not in _KNOWN_OPS:
        raise InvalidFrame("unknown opcode " + hex(op))
    if payload_len > MAX_PAYLOAD_LEN:
        raise InvalidFrame("declared payload " + str(payload_len) + " > cap")
    body = buf[_HEADER_LEN : _HEADER_LEN + payload_len]
    if len(body) < payload_len:
        raise InvalidFrame("payload truncated (expected " + str(payload_len) + ", got " + str(len(body)) + ")")
    return op, seq, bytes(body)
