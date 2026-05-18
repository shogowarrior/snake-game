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
