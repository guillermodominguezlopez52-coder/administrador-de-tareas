"""Recolector de procesos y utilidades de clasificación."""

from __future__ import annotations

import configparser
import os
import shlex
import time
from dataclasses import dataclass
from pathlib import Path

import psutil


STATUS_TEXT = {
    getattr(psutil, "STATUS_RUNNING", "running"): "En ejecución",
    getattr(psutil, "STATUS_SLEEPING", "sleeping"): "En espera",
    getattr(psutil, "STATUS_DISK_SLEEP", "disk-sleep"): "Esperando disco",
    getattr(psutil, "STATUS_STOPPED", "stopped"): "Suspendido",
    getattr(psutil, "STATUS_TRACING_STOP", "tracing-stop"): "Depuración detenida",
    getattr(psutil, "STATUS_ZOMBIE", "zombie"): "Zombi",
    getattr(psutil, "STATUS_DEAD", "dead"): "Finalizado",
    getattr(psutil, "STATUS_WAKING", "waking"): "Despertando",
    getattr(psutil, "STATUS_PARKED", "parked"): "Estacionado",
    getattr(psutil, "STATUS_IDLE", "idle"): "Inactivo",
    getattr(psutil, "STATUS_LOCKED", "locked"): "Bloqueado",
    getattr(psutil, "STATUS_WAITING", "waiting"): "Esperando",
}

KIND_TEXT = {
    "app": "Aplicación",
    "background": "Proceso en segundo plano",
    "service": "Servicio del sistema",
    "system": "Proceso del sistema",
}

KIND_ICON = {
    "app": "application-x-executable-symbolic",
    "background": "utilities-system-monitor-symbolic",
    "service": "emblem-system-symbolic",
    "system": "computer-symbolic",
}


def priority_text(nice: int) -> str:
    if nice <= -15:
        return "Muy alta"
    if nice < 0:
        return "Alta"
    if nice == 0:
        return "Normal"
    if nice <= 10:
        return "Baja"
    return "Muy baja"


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    ppid: int
    name: str
    username: str
    uid: int
    status: str
    status_text: str
    cpu_percent: float
    memory_rss: int
    memory_percent: float
    num_threads: int
    create_time: float
    cmdline: str
    exe: str
    nice: int
    priority_text: str
    io_read_bps: float
    io_write_bps: float
    kind: str
    kind_text: str
    icon: str


def _desktop_executables() -> set[str]:
    """Nombres de ejecutables registrados en lanzadores .desktop."""
    names: set[str] = set()
    home = Path.home()
    directories = [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        home / ".local/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        home / ".local/share/flatpak/exports/share/applications",
        Path("/var/lib/snapd/desktop/applications"),
    ]
    for directory in directories:
        try:
            files = list(directory.glob("*.desktop"))
        except OSError:
            continue
        for path in files:
            parser = configparser.ConfigParser(
                interpolation=None, strict=False, delimiters=("=",)
            )
            parser.optionxform = str
            try:
                parser.read(path, encoding="utf-8")
                if not parser.has_section("Desktop Entry"):
                    continue
                section = parser["Desktop Entry"]
            except (OSError, configparser.Error, UnicodeError):
                continue
            for key in ("Exec", "TryExec", "StartupWMClass"):
                value = section.get(key)
                if not value:
                    continue
                for token in shlex.split(value, posix=True):
                    if not token or token.startswith("-") or "=" in token:
                        continue
                    base = Path(token).name.strip().lower()
                    if len(base) >= 3:
                        names.add(base)
    return names


def _read_cgroup(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


class ProcessCollector:
    """Lista procesos manteniendo tasas de CPU y de disco entre muestras."""

    def __init__(self) -> None:
        self.cpu_count = psutil.cpu_count(logical=True) or 1
        self.user = os.environ.get("USER") or "usuario"
        self._desktop_names: set[str] | None = None
        self._kind_cache: dict[int, tuple[float, str]] = {}
        self._io_cache: dict[int, tuple[int, int]] = {}
        self._prev_time = time.monotonic()
        self._prime()

    def _prime(self) -> None:
        for process in psutil.process_iter():
            try:
                process.cpu_percent(None)
            except (psutil.Error, OSError):
                continue

    def _classify(
        self, pid: int, name: str, exe: str, cmdline: str, uid: int, create_time: float
    ) -> str:
        cached = self._kind_cache.get(pid)
        if cached and abs(cached[0] - create_time) < 0.001:
            return cached[1]

        kind = "background"
        cgroup = _read_cgroup(pid)
        name_lower = name.lower()
        exe_lower = Path(exe).name.lower() if exe else ""
        tokens = {
            Path(token).name.lower()
            for token in cmdline.split()
            if token and not token.startswith("-")
        }

        is_system_slice = "system.slice" in cgroup or "init.scope" in cgroup
        is_user_slice = "user.slice" in cgroup or "user@.service" in cgroup

        if pid == 1 or is_system_slice:
            kind = "service" if pid != 1 else "system"
        elif is_user_slice:
            desktop = self._desktop_names
            if desktop is None:
                desktop = self._desktop_names = _desktop_executables()
            if (
                name_lower in desktop
                or exe_lower in desktop
                or any(token in desktop for token in tokens)
            ):
                kind = "app"
            elif "app.slice" in cgroup or "app-" in cgroup:
                kind = "app"
            else:
                kind = "background"
        elif uid == os.getuid():
            desktop = self._desktop_names
            if desktop is None:
                desktop = self._desktop_names = _desktop_executables()
            if name_lower in desktop or exe_lower in desktop:
                kind = "app"
            else:
                kind = "background"
        else:
            kind = "system"

        self._kind_cache[pid] = (create_time, kind)
        return kind

    def collect(self) -> list[ProcessInfo]:
        now = time.monotonic()
        elapsed = max(now - self._prev_time, 0.001)
        attrs = [
            "pid",
            "ppid",
            "name",
            "username",
            "status",
            "cpu_percent",
            "memory_info",
            "memory_percent",
            "num_threads",
            "create_time",
            "cmdline",
            "exe",
            "nice",
            "io_counters",
            "uids",
        ]
        current_io: dict[int, tuple[int, int]] = {}
        result: list[ProcessInfo] = []
        seen: set[int] = set()

        try:
            iterator = psutil.process_iter(attrs=attrs, ad_value=None)
        except (psutil.Error, OSError):
            return result

        for process in iterator:
            info = getattr(process, "info", None)
            if not isinstance(info, dict):
                continue
            pid = info.get("pid")
            if not pid:
                continue
            seen.add(pid)
            try:
                name = info.get("name") or "?"
                cmdline_list = info.get("cmdline") or []
                cmdline = " ".join(cmdline_list) if cmdline_list else ""
                exe = info.get("exe") or ""
                if not cmdline:
                    cmdline = exe or name
                username = info.get("username") or "?"
                status = info.get("status") or psutil.STATUS_UNKNOWN
                memory = info.get("memory_info")
                memory_rss = int(memory.rss) if memory is not None else 0
                memory_percent = float(info.get("memory_percent") or 0.0)
                cpu_raw = float(info.get("cpu_percent") or 0.0)
                cpu = min(100.0, max(0.0, cpu_raw / self.cpu_count))
                nice = int(info.get("nice") or 0)
                uids = info.get("uids")
                uid = int(uids.real) if uids is not None else 0
                create_time = float(info.get("create_time") or 0.0)
                ppid = int(info.get("ppid") or 0)
                threads = int(info.get("num_threads") or 0)

                io = info.get("io_counters")
                read_bps = write_bps = 0.0
                if io is not None:
                    current_io[pid] = (int(io.read_bytes), int(io.write_bytes))
                    previous = self._io_cache.get(pid)
                    if previous:
                        read_bps = max(0.0, (io.read_bytes - previous[0]) / elapsed)
                        write_bps = max(0.0, (io.write_bytes - previous[1]) / elapsed)

                kind = self._classify(pid, name, exe, cmdline, uid, create_time)
                result.append(
                    ProcessInfo(
                        pid=pid,
                        ppid=ppid,
                        name=name,
                        username=username,
                        uid=uid,
                        status=status,
                        status_text=STATUS_TEXT.get(status, "Desconocido"),
                        cpu_percent=round(cpu, 1),
                        memory_rss=memory_rss,
                        memory_percent=round(memory_percent, 2),
                        num_threads=threads,
                        create_time=create_time,
                        cmdline=cmdline,
                        exe=exe,
                        nice=nice,
                        priority_text=priority_text(nice),
                        io_read_bps=read_bps,
                        io_write_bps=write_bps,
                        kind=kind,
                        kind_text=KIND_TEXT.get(kind, kind),
                        icon=KIND_ICON.get(kind, "application-x-executable-symbolic"),
                    )
                )
            except (psutil.Error, OSError, ValueError, TypeError):
                continue

        self._io_cache = current_io
        self._prev_time = now
        removable = [pid for pid in self._kind_cache if pid not in seen]
        for pid in removable:
            self._kind_cache.pop(pid, None)
        return result


__all__ = [
    "KIND_ICON",
    "KIND_TEXT",
    "ProcessCollector",
    "ProcessInfo",
    "STATUS_TEXT",
    "priority_text",
]
