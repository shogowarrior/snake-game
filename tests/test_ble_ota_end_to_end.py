"""End-to-end: host's encode_session -> in-memory pipe -> device Session -> commit."""

import asyncio
import sys
from pathlib import Path

# Import the host CLI module (lives under scripts/, not in src/).
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ble_ota  # noqa: E402
import ble_push  # noqa: E402
from ble_protocol import STAGING_DIR  # noqa: E402


class LoopbackTransport:
    """In-process transport: writes from host land directly in a device Session."""

    def __init__(self):
        self.session = ble_ota.Session()
        self._status_cb = None
        self.session.on_status = self._dispatch_status

    async def connect(self, name, timeout):
        return self

    async def disconnect(self):
        pass

    async def write_control(self, frame):
        self.session.handle_frame(frame)

    def on_status(self, cb):
        self._status_cb = cb

    def _dispatch_status(self, frame):
        if self._status_cb is not None:
            self._status_cb(frame)


def test_end_to_end_happy_path(tmp_path, monkeypatch):
    # Set up a fake repo layout under tmp_path.
    src = tmp_path / "src"
    (src / "embedded").mkdir(parents=True)
    (src / "common").mkdir(parents=True)
    (src / "embedded" / "main.py").write_bytes(b"print('hi from OTA')")
    (src / "common" / "engine.py").write_bytes(b"# engine v2")

    # Stub machine.soft_reset so the Session doesn't try to reboot the test runner.
    from unittest.mock import MagicMock

    import machine

    monkeypatch.setattr(machine, "soft_reset", MagicMock(), raising=False)

    # Run the device session in the tmp filesystem.
    monkeypatch.chdir(tmp_path)

    files = ble_push.collect_files(tmp_path)
    transport = LoopbackTransport()
    rc = asyncio.run(ble_push._push_async(files, name="snake-ota", timeout=2.0, transport=transport))

    assert rc == 0
    assert (tmp_path / "main.py").read_bytes() == b"print('hi from OTA')"
    assert (tmp_path / "common" / "engine.py").read_bytes() == b"# engine v2"
    assert not (tmp_path / STAGING_DIR).exists()
    assert transport.session.state == ble_ota.STATE_COMMITTED
