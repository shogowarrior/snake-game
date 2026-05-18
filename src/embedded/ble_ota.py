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
    OP_ABORT,
    OP_ACK,
    OP_BEGIN_FILE,
    OP_COMMIT,
    OP_END_FILE,
    OP_FILE_CHUNK,
    OP_MANIFEST,
    OP_NACK,
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
        # Actual commit pass is added in Task 10. For now: just transition.
        self.state = STATE_COMMITTED
        self._ack(seq)

    def _on_client_abort(self, seq):
        # Client-initiated; not a NACK situation. Just clean up.
        self.state = STATE_ABORTED
        self._cleanup_open_file()
        self._ack(seq)

    # ---- Helpers --------------------------------------------------------
    def _ack(self, seq):
        self.on_status(encode_frame(OP_ACK, seq, bytes([seq])))

    def _abort(self, reason, last_seq):
        self._cleanup_open_file()
        self.on_status(encode_frame(OP_NACK, last_seq, bytes([last_seq, reason])))
        self.state = STATE_ABORTED

    def _cleanup_open_file(self):
        if self._cur_staging_fh is not None:
            try:
                self._cur_staging_fh.close()
            except OSError:
                pass
            self._cur_staging_fh = None
