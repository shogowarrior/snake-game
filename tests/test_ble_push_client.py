"""Tests for scripts/ble_push.py — host-side OTA client. Bleak is mocked out."""

import sys
from pathlib import Path

# Make scripts/ importable like tests/conftest.py does for src/.
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ble_push  # noqa: E402


def test_collect_files_walks_src_embedded_and_common(tmp_path):
    (tmp_path / "src" / "embedded").mkdir(parents=True)
    (tmp_path / "src" / "common").mkdir(parents=True)
    (tmp_path / "src" / "embedded" / "main.py").write_text("# main")
    (tmp_path / "src" / "embedded" / "display.py").write_text("# display")
    (tmp_path / "src" / "common" / "engine.py").write_text("# engine")
    # File outside scope: should be ignored.
    (tmp_path / "src" / "common" / "__pycache__").mkdir()
    (tmp_path / "src" / "common" / "__pycache__" / "engine.cpython-311.pyc").write_bytes(b"\x00")
    (tmp_path / "src" / "desktop" / "main.py").parent.mkdir(parents=True)
    (tmp_path / "src" / "desktop" / "main.py").write_text("# desktop, skip")
    # __init__.py at common — embedded uses flat imports so common/__init__.py IS shipped.

    out = ble_push.collect_files(tmp_path)
    paths = sorted(p for p, _ in out)
    assert "main.py" in paths
    assert "display.py" in paths
    assert "common/engine.py" in paths
    # Desktop is excluded.
    assert "desktop/main.py" not in paths
    # __pycache__ is excluded.
    assert not any(".pyc" in p for p in paths)


def test_collect_files_returns_path_string_and_bytes(tmp_path):
    (tmp_path / "src" / "embedded").mkdir(parents=True)
    (tmp_path / "src" / "embedded" / "main.py").write_bytes(b"hello")
    out = ble_push.collect_files(tmp_path)
    assert all(isinstance(p, str) and isinstance(b, bytes) for p, b in out)
    assert dict(out)["main.py"] == b"hello"


def test_dry_run_main_prints_frames_without_connecting(tmp_path, capsys, monkeypatch):
    (tmp_path / "src" / "embedded").mkdir(parents=True)
    (tmp_path / "src" / "embedded" / "main.py").write_text("# main")
    monkeypatch.chdir(tmp_path)
    rc = ble_push.main_sync(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BEGIN_FILE" in out
    assert "COMMIT" in out


import asyncio  # noqa: E402

from ble_protocol import (  # noqa: E402
    NACK_BAD_CRC,
    OP_COMMITTED,
    OP_NACK,
    encode_frame,
)


class FakeTransport:
    """Stand-in for the bleak client. Records writes; replays scripted notifies."""

    def __init__(self, script=None):
        self.writes = []
        self._notify_cb = None
        # `script` maps frame index -> notification frame to deliver after that write.
        self._script = script or {}

    async def connect(self, name, timeout):
        return self  # context-manager-like

    async def disconnect(self):
        pass

    async def write_control(self, frame):
        self.writes.append(frame)
        idx = len(self.writes) - 1
        if idx in self._script:
            await asyncio.sleep(0)
            self._notify_cb(self._script[idx])

    def on_status(self, cb):
        self._notify_cb = cb


def test_push_succeeds_when_committed_status_arrives():
    files = [("main.py", b"hello")]
    # Send a COMMITTED notification as soon as our last frame (the COMMIT op) is written.
    # Build the script: index = len(frames)-1
    from ble_protocol import encode_session

    nframes = sum(1 for _ in encode_session(files))
    transport = FakeTransport(script={nframes - 1: encode_frame(OP_COMMITTED, 0, b"")})

    rc = asyncio.run(ble_push._push_async(files, name="snake-ota", timeout=1.0, transport=transport))
    assert rc == 0
    assert len(transport.writes) == nframes


def test_push_fails_on_nack(capsys):
    files = [("main.py", b"hello")]
    transport = FakeTransport(script={0: encode_frame(OP_NACK, 0, bytes([0, NACK_BAD_CRC]))})

    rc = asyncio.run(ble_push._push_async(files, name="snake-ota", timeout=1.0, transport=transport))
    assert rc == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "NACK" in out or "BAD_CRC" in out


def test_push_times_out_without_committed():
    files = [("main.py", b"x")]
    transport = FakeTransport(script={})  # no responses at all
    rc = asyncio.run(ble_push._push_async(files, name="snake-ota", timeout=0.1, transport=transport))
    assert rc == 1
