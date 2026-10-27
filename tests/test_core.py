"""Pruebas de la lógica que no requiere interfaz gráfica."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import psutil

from administrador_tareas.core import actions
from administrador_tareas.core.processes import (
    ProcessCollector,
    ProcessInfo,
    priority_text,
)
from administrador_tareas.core.services import ServiceInfo, run_action
from administrador_tareas.core.settings import Settings
from administrador_tareas.core.startup import (
    StartupEntry,
    list_startup_entries,
    set_startup_enabled,
)
from administrador_tareas.core.system import SystemMonitor


class SystemTests(unittest.TestCase):
    def test_monitor_snapshot(self) -> None:
        monitor = SystemMonitor()
        snapshot = monitor.sample()
        self.assertGreaterEqual(snapshot.cpu_percent, 0.0)
        self.assertLessEqual(snapshot.cpu_percent, 100.0)
        self.assertGreater(snapshot.mem_total, 0)
        self.assertGreaterEqual(snapshot.mem_percent, 0.0)
        self.assertLessEqual(snapshot.mem_percent, 100.0)
        self.assertEqual(len(snapshot.per_cpu), snapshot.cpu_count)
        self.assertGreaterEqual(snapshot.uptime, 0.0)


class ProcessTests(unittest.TestCase):
    def test_collector_contains_current_process(self) -> None:
        collector = ProcessCollector()
        processes = collector.collect()
        self.assertTrue(processes)
        current = next(
            (item for item in processes if item.pid == os.getpid()), None
        )
        self.assertIsNotNone(current)
        self.assertIsInstance(current, ProcessInfo)
        self.assertIn("python", current.name.lower() + current.cmdline.lower())
        self.assertGreaterEqual(current.memory_rss, 0)

    def test_priority_text(self) -> None:
        self.assertEqual(priority_text(0), "Normal")
        self.assertEqual(priority_text(10), "Baja")
        self.assertEqual(priority_text(-5), "Alta")

    def test_critical_self(self) -> None:
        self.assertTrue(actions.is_critical(os.getpid()))

    def test_end_nonexistent_process(self) -> None:
        with self.assertRaises(actions.ProcessActionError):
            actions.end_process(999999999)

    def test_process_actions_on_child(self) -> None:
        child = subprocess.Popen(["sleep", "30"])
        try:
            actions.set_process_nice(child.pid, 5)
            self.assertEqual(psutil.Process(child.pid).nice(), 5)

            actions.suspend_process(child.pid)
            status = ""
            for _ in range(40):
                status = psutil.Process(child.pid).status()
                if status == psutil.STATUS_STOPPED:
                    break
                time.sleep(0.05)
            self.assertEqual(status, psutil.STATUS_STOPPED)

            actions.resume_process(child.pid)
            for _ in range(40):
                status = psutil.Process(child.pid).status()
                if status != psutil.STATUS_STOPPED:
                    break
                time.sleep(0.05)
            self.assertNotEqual(status, psutil.STATUS_STOPPED)

            actions.end_process(child.pid)
            child.wait(timeout=5)
            self.assertIsNotNone(child.returncode)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    def test_details_for_current_process(self) -> None:
        details = actions.get_process_details(os.getpid())
        self.assertEqual(details.pid, os.getpid())
        self.assertIn("python", details.name.lower())
        self.assertIn("python", details.cmdline.lower())
        self.assertGreaterEqual(details.threads, 1)


class StartupTests(unittest.TestCase):
    def _write_desktop(self, directory: Path, name: str, extra: str = "") -> Path:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Prueba\n"
            "Comment=Entrada de prueba\n"
            f"Exec=/usr/bin/true\n{extra}",
            encoding="utf-8",
        )
        return path

    def test_list_and_toggle_user_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system = root / "system"
            system.mkdir()
            user_autostart = root / "autostart"
            user_autostart.mkdir()
            self._write_desktop(user_autostart, "usuario.desktop")
            with mock.patch.dict(
                os.environ, {"XDG_CONFIG_HOME": str(root)}
            ), mock.patch(
                "administrador_tareas.core.startup.SYSTEM_AUTOSTART", system
            ):
                entries = list_startup_entries()
                self.assertEqual(len(entries), 1)
                entry = entries[0]
                self.assertTrue(entry.enabled)
                self.assertEqual(entry.source, "Personal")
                set_startup_enabled(entry, False)
                entries = list_startup_entries()
                self.assertFalse(entries[0].enabled)
                set_startup_enabled(entries[0], True)
                entries = list_startup_entries()
                self.assertTrue(entries[0].enabled)

    def test_disable_system_entry_creates_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system = root / "system"
            config_home = root / "config"
            system.mkdir()
            config_home.mkdir()
            self._write_desktop(system, "sistema.desktop")
            with mock.patch.dict(
                os.environ, {"XDG_CONFIG_HOME": str(config_home)}
            ), mock.patch(
                "administrador_tareas.core.startup.SYSTEM_AUTOSTART", system
            ):
                entries = list_startup_entries()
                self.assertEqual(len(entries), 1)
                set_startup_enabled(entries[0], False)
                override = config_home / "autostart" / "sistema.desktop"
                self.assertTrue(override.exists())
                entries = list_startup_entries()
                self.assertFalse(entries[0].enabled)
                set_startup_enabled(entries[0], True)
                self.assertFalse(override.exists())
                entries = list_startup_entries()
                self.assertTrue(entries[0].enabled)


class ServicesTests(unittest.TestCase):
    def test_invalid_action(self) -> None:
        service = ServiceInfo(
            name="demo.service",
            description="Demo",
            load="loaded",
            active="inactive",
            sub="dead",
            enabled_state="disabled",
            scope="user",
        )
        with self.assertRaises(ValueError):
            run_action(service, "destroy")


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(path)
            self.assertEqual(settings.get("refresh_interval"), 2)
            settings.set("refresh_interval", 5)
            settings.set("color_scheme", "dark")
            loaded = Settings(path)
            self.assertEqual(loaded.get("refresh_interval"), 5)
            self.assertEqual(loaded.get("color_scheme"), "dark")

    def test_sanitize(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(path)
            settings.set("refresh_interval", 99)
            self.assertEqual(settings.get("refresh_interval"), 2)
            settings.set("color_scheme", "neon")
            self.assertEqual(settings.get("color_scheme"), "system")


if __name__ == "__main__":
    unittest.main()
