"""Device-side BLE OTA wiring. Imports the pure protocol layer from ble_protocol.

Top half: Session — a state machine that consumes wire frames and produces
status frames. No BLE, no filesystem; pure logic for testability.

Bottom half (Task 11): listen() — the GATT server, advertising loop, and IRQ
wiring that glues a Session to a real bluetooth.BLE instance and the on-disk
staging area.
"""

from ble_protocol import (
    MAX_FRAMES_PER_SESSION,
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
    STAGING_DIR,
    SYNCED_DIRS,
    SYNCED_TOP_LEVEL_GLOBS,
    FrameTooLarge,
    InvalidFrame,
    InvalidPath,
    ProtectedPath,
    decode_frame,
    encode_frame,
    parse_begin_file,
    validate_device_path,
)

# Session states
STATE_IDLE = "idle"
STATE_RECEIVING = "receiving"
STATE_BETWEEN_FILES = "between"
STATE_AWAITING_COMMIT = "await_commit"
STATE_COMMITTED = "committed"
STATE_ABORTED = "aborted"


class Session:
    """State machine for one OTA session. Frame in, status frames out via on_status."""

    def __init__(self):
        self.state = STATE_IDLE
        self.frames_received = 0
        self.on_status = lambda frame: None  # caller installs a callback
        # Current-file scratch:
        self._cur_path = None
        self._cur_size = None
        self._cur_crc = None
        self._cur_bytes_received = 0
        self._cur_crc_accum = 0
        self._cur_staging_fh = None
        # Cross-file scratch:
        self._manifest = []  # list of paths

    def handle_frame(self, frame):
        """Public entry: parse a frame from the wire and advance the state machine."""
        if self.state == STATE_ABORTED or self.state == STATE_COMMITTED:
            return  # ignore late frames after terminal state

        self.frames_received += 1
        if self.frames_received > MAX_FRAMES_PER_SESSION:
            self._abort(NACK_OVERSIZE, last_seq=0)
            return

        try:
            op, seq, payload = decode_frame(frame)
        except InvalidFrame:
            self._abort(NACK_OUT_OF_ORDER, last_seq=0)
            return

        # Dispatch by opcode + state. Any unexpected combination is an abort.
        try:
            if op == OP_BEGIN_FILE:
                self._on_begin(seq, payload)
            elif op == OP_FILE_CHUNK:
                self._on_chunk(seq, payload)
            elif op == OP_END_FILE:
                self._on_end(seq, payload)
            elif op == OP_MANIFEST:
                self._on_manifest(seq, payload)
            elif op == OP_COMMIT:
                self._on_commit(seq, payload)
            elif op == OP_ABORT:
                self._on_client_abort(seq)
            else:
                self._abort(NACK_OUT_OF_ORDER, last_seq=seq)
        except ProtectedPath:
            # Catch ProtectedPath BEFORE InvalidPath since it's a subclass.
            self._abort(NACK_PROTECTED, last_seq=seq)
        except InvalidPath:
            self._abort(NACK_BAD_PATH, last_seq=seq)
        except FrameTooLarge:
            self._abort(NACK_OVERSIZE, last_seq=seq)

    # ---- Opcode handlers ------------------------------------------------
    def _on_begin(self, seq, payload):
        if self.state not in (STATE_IDLE, STATE_BETWEEN_FILES):
            self._abort(NACK_OUT_OF_ORDER, last_seq=seq)
            return
        # parse_begin_file raises ProtectedPath / InvalidPath; the outer dispatcher
        # in handle_frame translates those into the correct NACK reason.
        path, size, crc = parse_begin_file(payload)
        self._cur_path = path
        self._cur_size = size
        self._cur_crc = crc
        self._cur_bytes_received = 0
        self._cur_crc_accum = 0
        # Open the staging file. Make parent dirs if needed.
        staging_path = STAGING_DIR + "/" + path
        try:
            _ensure_parent_dirs(staging_path)
            self._cur_staging_fh = open(staging_path, "wb")
        except OSError:
            self._abort(NACK_WRITE_FAILED, last_seq=seq)
            return
        self.state = STATE_RECEIVING
        self._ack(seq)

    def _on_chunk(self, seq, payload):
        if self.state != STATE_RECEIVING:
            self._abort(NACK_OUT_OF_ORDER, last_seq=seq)
            return
        self._cur_bytes_received += len(payload)
        if self._cur_bytes_received > self._cur_size:
            self._abort(NACK_OVERSIZE, last_seq=seq)
            return
        # Accumulate CRC incrementally. binascii.crc32 supports a "seed" param.
        from binascii import crc32

        self._cur_crc_accum = crc32(payload, self._cur_crc_accum) & 0xFFFFFFFF
        # File writing is added in Task 9 — for now, hold bytes in memory if needed.
        if self._cur_staging_fh is not None:
            self._cur_staging_fh.write(payload)
        self._ack(seq)

    def _on_end(self, seq, payload):
        if self.state != STATE_RECEIVING:
            self._abort(NACK_OUT_OF_ORDER, last_seq=seq)
            return
        if self._cur_bytes_received != self._cur_size:
            self._abort(NACK_OVERSIZE, last_seq=seq)
            return
        if self._cur_crc_accum != self._cur_crc:
            self._abort(NACK_BAD_CRC, last_seq=seq)
            return
        if self._cur_staging_fh is not None:
            self._cur_staging_fh.close()
            self._cur_staging_fh = None
        self.state = STATE_BETWEEN_FILES
        self._ack(seq)

    def _on_manifest(self, seq, payload):
        if self.state not in (STATE_IDLE, STATE_BETWEEN_FILES):
            self._abort(NACK_OUT_OF_ORDER, last_seq=seq)
            return
        try:
            paths = payload.decode("utf-8").split("\n") if payload else []
        except UnicodeError:
            self._abort(NACK_BAD_PATH, last_seq=seq)
            return
        # Validate every manifest entry up front; reject the whole session on any bad.
        # validate_device_path raises ProtectedPath for protected entries (subclass of
        # InvalidPath) — the outer try/except in handle_frame routes that to NACK_PROTECTED.
        for p in paths:
            validate_device_path(p)
        self._manifest = paths
        self.state = STATE_AWAITING_COMMIT
        self._ack(seq)

    def _on_commit(self, seq, payload):
        if self.state != STATE_AWAITING_COMMIT:
            self._abort(NACK_OUT_OF_ORDER, last_seq=seq)
            return
        try:
            _commit_pass(self._manifest)
        except OSError:
            self._abort(NACK_WRITE_FAILED, last_seq=seq)
            return
        self._ack(seq)
        self.on_status(encode_frame(OP_COMMITTED, seq, b""))
        self.state = STATE_COMMITTED
        _soft_reset()

    def _on_client_abort(self, seq):
        # Client-initiated; not a NACK situation. Just clean up.
        self.state = STATE_ABORTED
        self._cleanup_open_file()
        _wipe_staging()
        self._ack(seq)

    # ---- Helpers --------------------------------------------------------
    def _ack(self, seq):
        self.on_status(encode_frame(OP_ACK, seq, bytes([seq])))

    def _abort(self, reason, last_seq):
        self._cleanup_open_file()
        _wipe_staging()
        self.on_status(encode_frame(OP_NACK, last_seq, bytes([last_seq, reason])))
        self.state = STATE_ABORTED

    def _cleanup_open_file(self):
        if self._cur_staging_fh is not None:
            try:
                self._cur_staging_fh.close()
            except OSError:
                pass
            self._cur_staging_fh = None


# ---- Filesystem helpers --------------------------------------------
def _ensure_parent_dirs(path):
    """Create any missing parent directories for `path`. No-op if they exist.

    Works on MicroPython (only os.mkdir, no makedirs). Tolerates EEXIST.
    """
    import os

    parts = path.split("/")
    if len(parts) <= 1:
        return
    acc = ""
    for p in parts[:-1]:
        acc = (acc + "/" + p) if acc else p
        try:
            os.mkdir(acc)
        except OSError:
            # Exists or non-creatable; tolerated. If it's truly broken we'll
            # surface an OSError when we open the file.
            pass


def _wipe_staging():
    """Recursively remove STAGING_DIR. Best-effort: ignore individual unlink errors."""
    if not _exists(STAGING_DIR):
        return
    _rmtree(STAGING_DIR)


def _exists(path):
    import os

    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _rmtree(path):
    import os

    try:
        for entry in os.listdir(path):
            child = path + "/" + entry
            try:
                if _isdir(child):
                    _rmtree(child)
                else:
                    os.remove(child)
            except OSError:
                pass
        os.rmdir(path)
    except OSError:
        pass


def _isdir(path):
    import os

    try:
        return (os.stat(path)[0] & 0x4000) != 0  # S_IFDIR
    except OSError:
        return False


def _commit_pass(manifest):
    """Promote .staging/ files to root, prune anything in allowlist not in manifest."""
    import os

    # 1. Rename staged files into place.
    for path in manifest:
        staged = STAGING_DIR + "/" + path
        if _exists(staged):
            _ensure_parent_dirs(path)
            # Remove any existing destination first; some MicroPython os.rename
            # variants refuse to overwrite.
            if _exists(path) and not _isdir(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            os.rename(staged, path)

    # 2. Delete orphans in scope.
    manifest_set = set(manifest)
    for path in _list_allowlist_files():
        if path in PROTECTED_FILES:
            continue
        if path in manifest_set:
            continue
        try:
            os.remove(path)
        except OSError:
            pass

    # 3. Clean staging.
    _wipe_staging()


def _list_allowlist_files():
    """Yield existing paths under the synced-dirs allowlist (relative)."""
    import os

    # Top-level *.py
    try:
        for name in os.listdir("."):
            if _isdir(name):
                continue
            if any(_glob_match(name, g) for g in SYNCED_TOP_LEVEL_GLOBS):
                yield name
    except OSError:
        pass
    # One level deep under each SYNCED_DIRS entry
    for d in SYNCED_DIRS:
        try:
            for name in os.listdir(d):
                child = d + "/" + name
                if _isdir(child):
                    continue
                yield child
        except OSError:
            pass


def _glob_match(name, pattern):
    if pattern.startswith("*."):
        ext = pattern[1:]
        return name.endswith(ext) and len(name) > len(ext)
    return name == pattern


def _soft_reset():
    """Indirection so tests can monkey-patch machine.soft_reset."""
    import machine  # type: ignore

    machine.soft_reset()


# ---- BLE service definition (UUIDs are internal; not exposed via config) -----
SERVICE_UUID = b"\x00\xff\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
CONTROL_UUID = b"\x00\xff\x10\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
STATUS_UUID = b"\x00\xff\x10\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

# Indicator pixel position (top-left corner)
_INDICATOR_X = 0
_INDICATOR_Y = 0
_COLOR_ADVERTISING = (0, 0, 80)  # blue
_COLOR_CONNECTED = (0, 80, 80)  # cyan
_COLOR_OFF = (0, 0, 0)


# Test hook: overridden by tests to inject behavior once listen() is ready.
def _on_listen_ready(control_handle, status_handle):
    pass


def listen(timeout_secs, ble=None):
    """Boot-window BLE listen.

    Advertises for `timeout_secs`; if a central connects, fully drives a
    Session against the GATT characteristics until commit or abort. Returns
    True if a commit happened (caller should not see this — device soft-resets
    before this returns), False on timeout or abort.
    """
    import time

    from config import BLE_DEVICE_NAME

    if ble is None:
        import bluetooth  # type: ignore

        ble = bluetooth.BLE()

    ble.active(True)
    ble.config(gap_name=BLE_DEVICE_NAME)

    # MicroPython's bluetooth module exposes these flags as constants on the module.
    import bluetooth  # type: ignore

    flag_write = getattr(bluetooth, "FLAG_WRITE_NO_RESPONSE", 0x0004)
    flag_notify = getattr(bluetooth, "FLAG_NOTIFY", 0x0010)

    services = (
        (
            SERVICE_UUID,
            (
                (CONTROL_UUID, flag_write),
                (STATUS_UUID, flag_notify),
            ),
        ),
    )
    handles = ble.gatts_register_services(services)
    control_handle, status_handle = handles[0]

    session = Session()
    state = {"committed": False, "connected": False, "conn_handle": 0}

    def send_status(frame):
        try:
            ble.gatts_notify(state["conn_handle"], status_handle, frame)
        except OSError:
            pass

    session.on_status = send_status

    def irq(event, data):
        if event == 1:  # IRQ_CENTRAL_CONNECT
            conn_handle, _, _ = data
            state["connected"] = True
            state["conn_handle"] = conn_handle
            _set_indicator(_COLOR_CONNECTED)
            send_status(encode_frame(OP_READY, 0, b""))
        elif event == 2:  # IRQ_CENTRAL_DISCONNECT
            state["connected"] = False
            if session.state != STATE_COMMITTED:
                # Treat unexpected disconnect as abort: wipe staging, no reset.
                session._cleanup_open_file()
                _wipe_staging()
                session.state = STATE_ABORTED
        elif event == 3:  # IRQ_GATTS_WRITE
            _, value_handle = data
            if value_handle == control_handle:
                frame = ble.gatts_read(control_handle)
                session.handle_frame(frame)
                if session.state == STATE_COMMITTED:
                    state["committed"] = True

    ble.irq(irq)
    # Advertise (interval microseconds; real value irrelevant for fakes).
    if hasattr(ble, "gap_advertise"):
        ble.gap_advertise(100_000, adv_data=_adv_payload(BLE_DEVICE_NAME))
    _set_indicator(_COLOR_ADVERTISING)

    # Allow tests to inject frames right after the service is up.
    _on_listen_ready(control_handle, status_handle)

    # Wait loop: poll until either timeout elapses, a commit happened, or the
    # session aborted with no active connection.
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        if state["committed"]:
            _set_indicator(_COLOR_OFF)
            return True
        if session.state == STATE_ABORTED and not state["connected"]:
            _set_indicator(_COLOR_OFF)
            return False
        time.sleep(0.02)

    _set_indicator(_COLOR_OFF)
    # If we got here without a commit, ensure staging is clean (in case the
    # session was mid-flight and the central just stayed connected idle).
    if session.state != STATE_COMMITTED:
        _wipe_staging()
    return False


def _adv_payload(name):
    name_bytes = name.encode("utf-8")[:29]
    return bytes([len(name_bytes) + 1, 0x09]) + name_bytes  # 0x09 = complete local name


def _set_indicator(color):
    """Single-pixel visual cue. Tolerates a stubbed display in tests."""
    try:
        import display  # type: ignore

        display.set_pixel(_INDICATOR_X, _INDICATOR_Y, color)
        display.flush()
    except Exception:
        pass
