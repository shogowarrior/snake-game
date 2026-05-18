"""In-memory shim for MicroPython's `bluetooth` module.

Stands in for `bluetooth.BLE` under CPython tests so `ble_ota.listen()` can be
exercised without a radio. Mirrors the surface ble_ota.py actually calls; not
the full upstream API.

Test-only methods (`client_connect`, `client_disconnect`, `client_write`,
`register_characteristic`, `notifications_for`) drive the IRQ-style callback
that the device-side code registers via `BLE.irq(handler)`.
"""

# ---- IRQ event constants (subset of MicroPython's bluetooth module) ----
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3

# ---- GATT flag constants ----
FLAG_WRITE = 0x0008
FLAG_NOTIFY = 0x0010
FLAG_WRITE_NO_RESPONSE = 0x0004


class BLE:
    """Stand-in for `bluetooth.BLE`. Single-connection model: at most one central."""

    def __init__(self):
        self.is_active = False
        self.config_values = {}
        self._chars = {}  # handle -> last-written bytes
        self._notifications = {}  # handle -> list of bytes the device "sent"
        self._irq_handler = None
        self._next_handle = 1
        self._connected = False
        self._conn_handle = 0
        self._advertise_payload = None

    # ---- Surface that ble_ota.py uses ----------------------------------
    def active(self, on=True):
        self.is_active = bool(on)

    def config(self, **kw):
        self.config_values.update(kw)

    def gap_advertise(self, interval_us, adv_data=None):
        self._advertise_payload = adv_data

    def gatts_register_services(self, services):
        """Accept a list of services and return a tuple of tuples of handles.

        `services` shape (matches MicroPython): tuple of (uuid, characteristics)
        where characteristics is a tuple of (uuid, flags) tuples.
        """
        result = []
        for _service_uuid, chars in services:
            row = []
            for _char_uuid, _flags in chars:
                row.append(self._alloc_handle())
            result.append(tuple(row))
        return tuple(result)

    def gatts_write(self, handle, data):
        self._chars[handle] = bytes(data)

    def gatts_read(self, handle):
        return self._chars.get(handle, b"")

    def gatts_notify(self, conn_handle, value_handle, data):
        self._notifications.setdefault(value_handle, []).append(bytes(data))

    def irq(self, handler):
        self._irq_handler = handler

    # ---- Test-only API -------------------------------------------------
    def register_characteristic(self, uuid_bytes=b""):
        """Bypass full service registration: allocate a single handle for tests."""
        h = self._alloc_handle()
        self._chars[h] = b""
        return h

    def client_connect(self):
        self._connected = True
        self._dispatch(IRQ_CENTRAL_CONNECT, (self._conn_handle, 0, b"\x00" * 6))

    def client_disconnect(self):
        self._connected = False
        self._dispatch(IRQ_CENTRAL_DISCONNECT, (self._conn_handle, 0, b"\x00" * 6))

    def client_write(self, handle, data):
        if not self._connected:
            self.client_connect()
        self._chars[handle] = bytes(data)
        self._dispatch(IRQ_GATTS_WRITE, (self._conn_handle, handle))

    def notifications_for(self, handle):
        return list(self._notifications.get(handle, []))

    # ---- Internals -----------------------------------------------------
    def _alloc_handle(self):
        h = self._next_handle
        self._next_handle += 1
        return h

    def _dispatch(self, event, data):
        if self._irq_handler is not None:
            self._irq_handler(event, data)
