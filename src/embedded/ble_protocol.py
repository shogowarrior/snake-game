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
