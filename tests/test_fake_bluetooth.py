"""Smoke tests for the fake bluetooth shim. Verifies enough of the surface that
ble_ota.listen() can call the same methods it would on real hardware."""

from sim import fake_bluetooth


def test_ble_class_supports_active_and_config():
    ble = fake_bluetooth.BLE()
    ble.active(True)
    ble.config(gap_name="snake-ota")
    assert ble.is_active is True
    assert ble.config_values["gap_name"] == "snake-ota"


def test_irq_handler_registered_and_invoked_on_client_connect():
    ble = fake_bluetooth.BLE()
    events = []
    ble.irq(lambda event, data: events.append((event, data)))
    ble.client_connect()
    assert events
    assert events[0][0] == fake_bluetooth.IRQ_CENTRAL_CONNECT


def test_client_write_invokes_irq_with_handle_and_value():
    ble = fake_bluetooth.BLE()
    handle = ble.register_characteristic(b"\x01\x02")  # arbitrary uuid bytes for test
    captured = []
    ble.irq(lambda event, data: captured.append((event, data)))
    ble.client_write(handle, b"hello")
    assert captured[-1][0] == fake_bluetooth.IRQ_GATTS_WRITE
    conn, value_handle = captured[-1][1]
    assert value_handle == handle
    assert ble.gatts_read(handle) == b"hello"


def test_gatts_notify_records_payload_for_test_inspection():
    ble = fake_bluetooth.BLE()
    handle = ble.register_characteristic(b"\xaa\xbb")
    ble.client_connect()
    ble.gatts_notify(0, handle, b"ack")
    assert ble.notifications_for(handle) == [b"ack"]


def test_module_exports_match_micropython_bluetooth_surface():
    # Just enough to spot-check we expose the right symbol names.
    assert hasattr(fake_bluetooth, "BLE")
    assert hasattr(fake_bluetooth, "IRQ_CENTRAL_CONNECT")
    assert hasattr(fake_bluetooth, "IRQ_CENTRAL_DISCONNECT")
    assert hasattr(fake_bluetooth, "IRQ_GATTS_WRITE")
    assert hasattr(fake_bluetooth, "FLAG_WRITE")
    assert hasattr(fake_bluetooth, "FLAG_NOTIFY")
