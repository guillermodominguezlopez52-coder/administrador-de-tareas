"""Lectura de métricas globales del sistema con psutil."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil


@dataclass(slots=True)
class SystemSnapshot:
    cpu_percent: float = 0.0
    per_cpu: list[float] = field(default_factory=list)
    cpu_count: int = 1
    cpu_freq_mhz: float = 0.0
    cpu_freq_max: float = 0.0
    cpu_temp: float | None = None
    load_avg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mem_total: int = 0
    mem_used: int = 0
    mem_available: int = 0
    mem_percent: float = 0.0
    mem_cached: int = 0
    swap_total: int = 0
    swap_used: int = 0
    swap_percent: float = 0.0
    disk_read_bps: float = 0.0
    disk_write_bps: float = 0.0
    disk_percent: float = 0.0
    disk_total: int = 0
    disk_used: int = 0
    disk_free: int = 0
    net_up_bps: float = 0.0
    net_down_bps: float = 0.0
    net_iface: str = ""
    net_ip: str = ""
    net_mac: str = ""
    net_speed: int = 0
    uptime: float = 0.0
    boot_time: float = 0.0


def _safe_cpu_freq() -> tuple[float, float]:
    try:
        freq = psutil.cpu_freq()
    except (AttributeError, NotImplementedError, OSError):
        return 0.0, 0.0
    if not freq:
        return 0.0, 0.0
    return float(freq.current or 0.0), float(freq.max or 0.0)


def _cpu_temperature() -> float | None:
    try:
        sensors = psutil.sensors_temperatures()
    except (AttributeError, OSError, TypeError):
        return None
    preferred = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz")
    for key in preferred:
        for entry in sensors.get(key, []):
            if entry.current is not None:
                return float(entry.current)
    values = [
        float(entry.current)
        for entries in sensors.values()
        for entry in entries
        if entry.current is not None
    ]
    return max(values) if values else None


def _default_interface() -> str:
    """Obtiene la interfaz de red usada por la ruta predeterminada."""
    try:
        for line in Path("/proc/net/route").read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split()
            if len(fields) > 2 and fields[1] == "00000000":
                return fields[0]
    except OSError:
        pass
    stats = psutil.net_if_stats()
    for name, info in stats.items():
        if name != "lo" and info.isup:
            return name
    return ""


def _interface_details(name: str) -> tuple[str, str, int]:
    if not name:
        return "", "", 0
    ip = ""
    mac = ""
    try:
        for addr in psutil.net_if_addrs().get(name, []):
            family = getattr(addr, "family", None)
            if family == socket.AF_INET and not ip:
                ip = addr.address
            elif family == getattr(socket, "AF_PACKET", -2) and not mac:
                mac = addr.address
    except (OSError, AttributeError):
        pass
    speed = 0
    try:
        speed = int(psutil.net_if_stats().get(name).speed or 0)
    except (AttributeError, OSError):
        pass
    return ip, mac, speed


class SystemMonitor:
    """Toma muestras periódicas y calcula velocidades por diferencia."""

    def __init__(self) -> None:
        self.cpu_count = psutil.cpu_count(logical=True) or 1
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)
        self._prev_time = time.monotonic()
        self._prev_disk = psutil.disk_io_counters()
        self._prev_net = psutil.net_io_counters()
        self._boot_time = psutil.boot_time()

    def sample(self) -> SystemSnapshot:
        now = time.monotonic()
        elapsed = max(now - self._prev_time, 0.001)

        cpu_percent = psutil.cpu_percent(interval=None)
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        freq_mhz, freq_max = _safe_cpu_freq()

        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        used = max(0, mem.total - mem.available)
        used_percent = (used / mem.total * 100.0) if mem.total else 0.0

        disk = psutil.disk_io_counters()
        read_bps = write_bps = 0.0
        if disk and self._prev_disk:
            read_bps = max(0.0, (disk.read_bytes - self._prev_disk.read_bytes) / elapsed)
            write_bps = max(0.0, (disk.write_bytes - self._prev_disk.write_bytes) / elapsed)
        if disk:
            self._prev_disk = disk

        net = psutil.net_io_counters()
        up_bps = down_bps = 0.0
        if net and self._prev_net:
            up_bps = max(0.0, (net.bytes_sent - self._prev_net.bytes_sent) / elapsed)
            down_bps = max(0.0, (net.bytes_recv - self._prev_net.bytes_recv) / elapsed)
        if net:
            self._prev_net = net

        try:
            usage = psutil.disk_usage("/")
            disk_total, disk_used, disk_free, disk_percent = (
                usage.total,
                usage.used,
                usage.free,
                usage.percent,
            )
        except OSError:
            disk_total = disk_used = disk_free = 0
            disk_percent = 0.0

        try:
            load_avg = os.getloadavg()
        except (OSError, AttributeError):
            load_avg = (0.0, 0.0, 0.0)

        iface = _default_interface()
        ip, mac, speed = _interface_details(iface)

        snapshot = SystemSnapshot(
            cpu_percent=cpu_percent,
            per_cpu=per_cpu,
            cpu_count=self.cpu_count,
            cpu_freq_mhz=freq_mhz,
            cpu_freq_max=freq_max,
            cpu_temp=_cpu_temperature(),
            load_avg=load_avg,
            mem_total=mem.total,
            mem_used=used,
            mem_available=mem.available,
            mem_percent=used_percent,
            mem_cached=int(getattr(mem, "cached", 0) + getattr(mem, "buffers", 0)),
            swap_total=swap.total,
            swap_used=swap.used,
            swap_percent=swap.percent,
            disk_read_bps=read_bps,
            disk_write_bps=write_bps,
            disk_percent=disk_percent,
            disk_total=disk_total,
            disk_used=disk_used,
            disk_free=disk_free,
            net_up_bps=up_bps,
            net_down_bps=down_bps,
            net_iface=iface,
            net_ip=ip,
            net_mac=mac,
            net_speed=speed,
            uptime=max(0.0, time.time() - self._boot_time),
            boot_time=self._boot_time,
        )
        self._prev_time = now
        return snapshot


__all__ = ["SystemMonitor", "SystemSnapshot"]
