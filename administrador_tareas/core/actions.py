"""Acciones sobre procesos: finalizar, suspender, prioridad y detalles."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

CRITICAL_NAMES = {
    "systemd",
    "init",
    "gnome-shell",
    "mutter",
    "kwin_wayland",
    "kwin_x11",
    "plasmashell",
    "xfwm4",
    "Xorg",
    "Xwayland",
    "wayland",
    "dbus-daemon",
    "dbus-broker",
    "pipewire",
    "wireplumber",
    "gdm",
    "gdm3",
    "sddm",
    "lightdm",
}


class ProcessActionError(RuntimeError):
    pass


def get_process(pid: int) -> psutil.Process:
    try:
        return psutil.Process(pid)
    except psutil.NoSuchProcess as error:
        raise ProcessActionError("El proceso ya no existe.") from error


def is_critical(pid: int) -> bool:
    if pid <= 1 or pid == os.getpid() or pid == os.getppid():
        return True
    try:
        name = psutil.Process(pid).name()
    except psutil.Error:
        return False
    return name in CRITICAL_NAMES


def process_tree(pid: int) -> list[psutil.Process]:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess as error:
        raise ProcessActionError("El proceso ya no existe.") from error
    try:
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []
    return children + [parent]


def end_process(pid: int, force: bool = False) -> None:
    process = get_process(pid)
    try:
        if force:
            process.kill()
        else:
            process.terminate()
    except psutil.NoSuchProcess:
        raise ProcessActionError("El proceso ya no existe.")
    except psutil.AccessDenied as error:
        raise PermissionError("Se necesitan permisos de administrador.") from error
    except psutil.Error as error:
        raise ProcessActionError(str(error)) from error


def end_process_tree(pid: int, force: bool = False) -> list[int]:
    processes = process_tree(pid)
    for process in processes:
        try:
            if force:
                process.kill()
            else:
                process.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as error:
            raise PermissionError("Se necesitan permisos de administrador.") from error
        except psutil.Error:
            continue
    return [process.pid for process in processes]


def suspend_process(pid: int) -> None:
    process = get_process(pid)
    try:
        process.suspend()
    except psutil.NoSuchProcess:
        raise ProcessActionError("El proceso ya no existe.")
    except psutil.AccessDenied as error:
        raise PermissionError("Se necesitan permisos de administrador.") from error
    except psutil.Error as error:
        raise ProcessActionError(str(error)) from error


def resume_process(pid: int) -> None:
    process = get_process(pid)
    try:
        process.resume()
    except psutil.NoSuchProcess:
        raise ProcessActionError("El proceso ya no existe.")
    except psutil.AccessDenied as error:
        raise PermissionError("Se necesitan permisos de administrador.") from error
    except psutil.Error as error:
        raise ProcessActionError(str(error)) from error


def set_process_nice(pid: int, nice: int) -> None:
    process = get_process(pid)
    try:
        process.nice(nice)
    except psutil.NoSuchProcess:
        raise ProcessActionError("El proceso ya no existe.")
    except psutil.AccessDenied as error:
        raise PermissionError("Se necesitan permisos de administrador.") from error
    except psutil.Error as error:
        raise ProcessActionError(str(error)) from error


def admin_end_command(pid: int, force: bool = False) -> list[str]:
    return ["pkexec", "kill", "-KILL" if force else "-TERM", str(pid)]


def admin_tree_command(pids: list[int], force: bool = False) -> list[str]:
    return ["pkexec", "kill", "-KILL" if force else "-TERM"] + [str(pid) for pid in pids]


def admin_suspend_command(pid: int, resume: bool = False) -> list[str]:
    return ["pkexec", "kill", "-CONT" if resume else "-STOP", str(pid)]


def admin_nice_command(pid: int, nice: int) -> list[str]:
    return ["pkexec", "renice", "-n", str(nice), "-p", str(pid)]


def run_command(command: list[str], timeout: float = 90.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return False, "No se encontró el programa necesario en el sistema."
    except subprocess.TimeoutExpired:
        return False, "La operación tardó demasiado."
    except OSError as error:
        return False, f"No se pudo ejecutar la operación: {error}"
    if result.returncode == 0:
        return True, ""
    if result.returncode in (126, 127):
        return False, "La operación se canceló o no se concedieron permisos."
    message = (result.stderr or result.stdout or "").strip()
    return False, message or "No se pudo completar la operación."


@dataclass(slots=True)
class ProcessDetails:
    pid: int
    name: str
    exe: str
    cwd: str
    cmdline: str
    username: str
    status: str
    started: str
    threads: int
    priority: str
    open_files: int
    connections: int
    memory_rss: int
    cpu_time: float
    parent: int
    warnings: list[str] = field(default_factory=list)


def get_process_details(pid: int) -> ProcessDetails:
    process = get_process(pid)
    try:
        info = process.as_dict(
            attrs=[
                "pid",
                "name",
                "exe",
                "cwd",
                "cmdline",
                "username",
                "status",
                "create_time",
                "num_threads",
                "nice",
                "memory_info",
                "cpu_times",
                "ppid",
            ],
            ad_value=None,
        )
    except psutil.NoSuchProcess as error:
        raise ProcessActionError("El proceso ya no existe.") from error
    except psutil.Error as error:
        raise ProcessActionError(str(error)) from error

    warnings: list[str] = []
    try:
        open_files = len(process.open_files())
    except psutil.Error:
        open_files = 0
        warnings.append("No se pudo leer la lista de archivos abiertos.")
    try:
        connections = len(process.net_connections(kind="inet"))
    except psutil.Error:
        connections = 0
        warnings.append("No se pudieron leer las conexiones de red.")

    memory = info.get("memory_info")
    cpu_times = info.get("cpu_times")
    started = ""
    if info.get("create_time"):
        started = time.strftime(
            "%d/%m/%Y %H:%M:%S", time.localtime(info["create_time"])
        )
    nice = int(info.get("nice") or 0)
    if nice <= -15:
        priority = f"Muy alta ({nice})"
    elif nice < 0:
        priority = f"Alta ({nice})"
    elif nice == 0:
        priority = "Normal (0)"
    elif nice <= 10:
        priority = f"Baja ({nice})"
    else:
        priority = f"Muy baja ({nice})"

    cpu_time = 0.0
    if cpu_times is not None:
        try:
            cpu_time = float(cpu_times.user + cpu_times.system)
        except (TypeError, AttributeError):
            cpu_time = 0.0

    return ProcessDetails(
        pid=int(info.get("pid") or pid),
        name=info.get("name") or "?",
        exe=info.get("exe") or "",
        cwd=info.get("cwd") or "",
        cmdline=" ".join(info.get("cmdline") or []),
        username=info.get("username") or "?",
        status=info.get("status") or "",
        started=started,
        threads=int(info.get("num_threads") or 0),
        priority=priority,
        open_files=open_files,
        connections=connections,
        memory_rss=int(memory.rss) if memory is not None else 0,
        cpu_time=cpu_time,
        parent=int(info.get("ppid") or 0),
        warnings=warnings,
    )


def open_executable_location(exe: str) -> bool:
    if not exe:
        return False
    path = Path(exe)
    if path.exists():
        target = path.parent
    else:
        return False
    try:
        subprocess.Popen(
            ["xdg-open", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def send_signal(pid: int, sig: signal.Signals) -> None:
    try:
        os.kill(pid, sig)
    except ProcessLookupError as error:
        raise ProcessActionError("El proceso ya no existe.") from error
    except PermissionError as error:
        raise PermissionError("Se necesitan permisos de administrador.") from error


__all__ = [
    "ProcessActionError",
    "ProcessDetails",
    "admin_end_command",
    "admin_nice_command",
    "admin_suspend_command",
    "admin_tree_command",
    "end_process",
    "end_process_tree",
    "get_process_details",
    "is_critical",
    "open_executable_location",
    "process_tree",
    "resume_process",
    "run_command",
    "send_signal",
    "set_process_nice",
    "suspend_process",
]
