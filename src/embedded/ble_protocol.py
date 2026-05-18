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


# ---- Path validation ---------------------------------------------


def validate_device_path(path):
    """Reject anything that isn't a legal, allowlist-conforming, non-protected device path.

    Allowed shapes:
      - Top-level: matches one of SYNCED_TOP_LEVEL_GLOBS (currently *.py).
      - In a synced dir: "<dir>/<file>.py" where <dir> in SYNCED_DIRS, exactly one slash.

    Rejected: empty, absolute, "..", embedded null, over MAX_PATH_LEN-1 chars (we add a null
    terminator on the wire), protected names, or anything outside the allowlist.

    Raises InvalidPath on rejection.
    """
    if not path:
        raise InvalidPath("empty path")
    if len(path) > MAX_PATH_LEN - 1:  # -1 for trailing null on the wire
        raise InvalidPath("path too long: " + str(len(path)) + " > " + str(MAX_PATH_LEN - 1))
    if "\x00" in path:
        raise InvalidPath("embedded null")
    if path.startswith("/"):
        raise InvalidPath("absolute path: " + path)
    parts = path.split("/")
    if ".." in parts:
        raise InvalidPath("traversal: " + path)
    if any(p == "." for p in parts):
        raise InvalidPath("current-dir segment: " + path)
    if "" in parts:
        raise InvalidPath("empty segment: " + path)

    if path in PROTECTED_FILES:
        raise ProtectedPath("protected: " + path)

    # Classify: top-level or one-level-deep in a synced dir.
    if "/" not in path:
        # Top-level — must match one of the globs.
        if not any(_glob_match(path, g) for g in SYNCED_TOP_LEVEL_GLOBS):
            raise InvalidPath("top-level path not in allowlist: " + path)
        return

    if path.count("/") > 1:
        raise InvalidPath("nested beyond one level: " + path)
    dir_part, file_part = path.split("/", 1)
    if dir_part not in SYNCED_DIRS:
        raise InvalidPath("dir not in SYNCED_DIRS: " + dir_part)
    if not file_part.endswith(".py"):
        raise InvalidPath("non-.py file in synced dir: " + path)
    if not file_part or file_part == ".py":
        raise InvalidPath("empty filename: " + path)


def _glob_match(name, pattern):
    """Tiny *.ext matcher. MicroPython has no fnmatch; this covers our one case."""
    if pattern.startswith("*."):
        ext = pattern[1:]  # ".py"
        return name.endswith(ext) and len(name) > len(ext)
    return name == pattern


# ---- BEGIN_FILE payload codec ------------------------------------
# Layout: [u32 size LE][u32 crc32 LE][utf-8 path][\0]


def encode_begin_file(path, size, crc):
    """Build the BEGIN_FILE payload. Validates the path and size."""
    validate_device_path(path)
    if size < 0 or size > MAX_FILE_SIZE:
        raise InvalidPath("size out of range: " + str(size))
    path_bytes = path.encode("utf-8")
    return (size & 0xFFFFFFFF).to_bytes(4, "little") + (crc & 0xFFFFFFFF).to_bytes(4, "little") + path_bytes + b"\x00"


def parse_begin_file(payload):
    """Decode a BEGIN_FILE payload -> (path, size, crc). Validates the path."""
    if len(payload) < 8 + 1:  # 4+4 + at least null
        raise InvalidFrame("BEGIN_FILE payload too short")
    size = int.from_bytes(payload[0:4], "little")
    crc = int.from_bytes(payload[4:8], "little")
    rest = payload[8:]
    nul = rest.find(b"\x00")
    if nul < 0:
        raise InvalidFrame("BEGIN_FILE missing null terminator")
    if nul != len(rest) - 1:
        raise InvalidFrame("BEGIN_FILE has bytes after null terminator")
    try:
        path = rest[:nul].decode("utf-8")
    except UnicodeError:
        raise InvalidFrame("BEGIN_FILE path is not utf-8")
    validate_device_path(path)
    return path, size, crc


# ---- CRC32 wrapper (consistent with binascii.crc32) ----------------
def compute_crc32(data):
    """Match binascii.crc32 semantics: unsigned, masked to 32 bits."""
    from binascii import crc32

    return crc32(data) & 0xFFFFFFFF


# ---- Session encoder ----------------------------------------------
def encode_session(files):
    """Yield the full frame sequence for a sync session.

    `files` is an iterable of (device_path, bytes). Order is preserved:
    files are sent in the given order, then a single MANIFEST listing them
    in the same order, then a single COMMIT.

    Raises InvalidPath if any path fails validation.
    """
    seq = 0

    def step():
        nonlocal seq
        cur = seq
        seq = (seq + 1) & 0xFF
        return cur

    manifest_paths = []
    for path, body in files:
        validate_device_path(path)
        size = len(body)
        if size > MAX_FILE_SIZE:
            raise InvalidPath("file " + path + " too big: " + str(size))
        manifest_paths.append(path)

        yield encode_frame(OP_BEGIN_FILE, step(), encode_begin_file(path, size, compute_crc32(body)))

        # Chunk body into MAX_PAYLOAD_LEN-sized pieces. Zero-byte files still
        # emit at least one (empty) CHUNK so the receiver sees the END marker
        # cleanly bracket a body.
        if size == 0:
            yield encode_frame(OP_FILE_CHUNK, step(), b"")
        else:
            i = 0
            while i < size:
                chunk = body[i : i + MAX_PAYLOAD_LEN]
                yield encode_frame(OP_FILE_CHUNK, step(), chunk)
                i += MAX_PAYLOAD_LEN

        yield encode_frame(OP_END_FILE, step(), b"")

    manifest_payload = "\n".join(manifest_paths).encode("utf-8")
    yield encode_frame(OP_MANIFEST, step(), manifest_payload)
    yield encode_frame(OP_COMMIT, step(), b"")
