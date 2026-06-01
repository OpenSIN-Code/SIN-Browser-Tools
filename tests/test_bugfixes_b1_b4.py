"""Tests for B1-B4 bugfixes: config, headful, signal handler, zombie cleanup."""

import os
import pytest
import asyncio
from sin_browser_tools.opensin_config import get_config, reset_config
from sin_browser_tools.core.manager import BrowserManager


class TestB1Config:
    """B1: opensin_config.py liest SIN_* Env-Vars."""

    def test_config_reads_sin_headless_env(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("SIN_HEADLESS", "false")
        cfg = get_config()
        assert cfg.headless is False

    def test_config_reads_sin_headless_true_variations(self, monkeypatch):
        for val in ("1", "true", "yes", "on"):
            reset_config()
            monkeypatch.setenv("SIN_HEADLESS", val)
            cfg = get_config()
            assert cfg.headless is True, f"failed for {val}"

    def test_config_reads_sin_viewport_dims(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("SIN_VIEWPORT_WIDTH", "2560")
        monkeypatch.setenv("SIN_VIEWPORT_HEIGHT", "1440")
        cfg = get_config()
        assert cfg.viewport_width == 2560
        assert cfg.viewport_height == 1440

    def test_config_defaults_when_unset(self, monkeypatch):
        reset_config()
        monkeypatch.delenv("SIN_HEADLESS", raising=False)
        monkeypatch.delenv("SIN_STEALTH", raising=False)
        cfg = get_config()
        assert cfg.headless is True  # default
        assert cfg.stealth is True   # default

    def test_config_reads_sin_auto_record_on_failure(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("SIN_AUTO_RECORD_ON_FAILURE", "false")
        cfg = get_config()
        assert cfg.auto_record_on_failure is False


class TestB2B3Manager:
    """B2+B3: Manager constructor + Signal Handler."""

    def test_manager_respects_explicit_headless_arg(self):
        """Explizites Arg > Config."""
        mgr = BrowserManager(headless=True)
        assert mgr.headless is True
        mgr2 = BrowserManager(headless=False)
        assert mgr2.headless is False

    def test_manager_reads_config_when_arg_none(self, monkeypatch):
        """Arg is None -> Config konsultieren."""
        reset_config()
        monkeypatch.setenv("SIN_HEADLESS", "false")
        mgr = BrowserManager(headless=None)  # explicit None
        assert mgr.headless is False

    def test_manager_signal_handler_installed(self):
        """Signal-Handler wird installiert ohne Exception."""
        mgr = BrowserManager()
        # Kein Exception = ok (kann die Handler nicht direkt testen ohne signal.alarm)
        assert mgr is not None


@pytest.mark.asyncio
class TestB4ZombieCleanup:
    """B4: _kill_zombie_processes mit Windows-Unterstützung."""

    async def test_zombie_cleanup_noop_when_no_pid(self):
        """Keine Exception wenn _browser_pid is None."""
        mgr = BrowserManager()
        mgr._browser_pid = None
        await mgr._kill_zombie_processes()  # should not raise

    async def test_zombie_cleanup_handles_posix(self):
        """POSIX-Pfad wird aufgerufen (mock: einfach checken dass es nicht crashed)."""
        if os.name != "posix":
            pytest.skip("POSIX-only")
        mgr = BrowserManager()
        mgr._browser_pid = 999999  # fake PID (existiert nicht -> kill fehlschlag)
        await mgr._kill_zombie_processes()  # should not raise


class TestB1B2Integration:
    """Integration: Config wird von Manager gelesen."""

    def test_manager_uses_config_executable_path(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("SIN_BROWSER_EXECUTABLE", "/custom/chromium")
        mgr = BrowserManager()
        assert mgr.executable_path == "/custom/chromium"

    def test_manager_uses_config_auto_record(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("SIN_AUTO_RECORD_ON_FAILURE", "true")
        mgr = BrowserManager()
        assert mgr.auto_record_on_failure is True
