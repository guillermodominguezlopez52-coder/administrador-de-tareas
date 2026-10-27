"""Servicios de systemd (sistema y sesión del usuario)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

ACTIVE_TEXT = {
    "running": "En ejecución",
    "exited": "Finalizado correctamente",
    "dead": "Detenido",
    "failed": "Con errores",
    "activating": "Iniciando",
    "deactivating": "Deteniendo",
    "reloading": "Recargando",
    "start-pre": "Iniciando",
    "start": "Iniciando",
    "stop": "Deteniendo",
    "auto-restart": "Reiniciando",
}

ENABLED_TEXT = {
    "enabled": "Habilitado",
    "disabled": "Deshabilitado",
    "static": "Estático",
    "masked": "Enmascarado",
    "enabled-runtime": "Habilitado (temporal)",
    "generated": "Generado",
    "indirect": "Indirecto",
    "alias": "Alias",
    "transient": "Temporal",
    "bad": "Estado desconocido",
}


@dataclass(slots=True)
class ServiceInfo:
    name: str
    description: str
    load: str
    active: str
    sub: str
    enabled_state: str
    scope: str

    @property
    def state_text(self) -> str:
        if self.active == "failed":
            return "Con errores"
        if self.active == "active":
            return ACTIVE_TEXT.get(self.sub, "Activo")
        if self.active == "inactive":
            return "Detenido"
        return ACTIVE_TEXT.get(self.active, self.active or "Desconocido")

    @property
    def enabled_text(self) -> str:
        return ENABLED_TEXT.get(self.enabled_state, self.enabled_state or "Desconocido")

    @property
    def scope_text(self) -> str:
        return "Sistema" if self.scope == "system" else "Usuario"

    @property
    def is_running(self) -> bool:
        return self.active == "active"

    @property
    def is_failed(self) -> bool:
        return self.active == "failed"


def _run(args: list[str], timeout: float = 8.0) -> str:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _unit_files(scope: str) -> dict[str, str]:
    command = ["systemctl"]
    if scope == "user":
        command.append("--user")
    command += [
        "list-unit-files",
        "--type=service",
        "--no-legend",
        "--no-pager",
        "--plain",
    ]
    output = _run(command)
    states: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].endswith(".service"):
            states[fields[0]] = fields[1]
    return states


def _list_units(scope: str) -> list[ServiceInfo]:
    command = ["systemctl"]
    if scope == "user":
        command.append("--user")
    command += [
        "list-units",
        "--type=service",
        "--all",
        "--no-legend",
        "--no-pager",
        "--plain",
    ]
    output = _run(command)
    states = _unit_files(scope)
    services: list[ServiceInfo] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        fields = line.split(None, 4)
        if len(fields) < 4 or not fields[0].endswith(".service"):
            continue
        name, load, active, sub = fields[:4]
        description = fields[4].strip() if len(fields) > 4 else ""
        if load in ("not-found", "masked") and active == "inactive":
            continue
        services.append(
            ServiceInfo(
                name=name,
                description=description,
                load=load,
                active=active,
                sub=sub,
                enabled_state=states.get(name, ""),
                scope=scope,
            )
        )
    return services


def list_services() -> list[ServiceInfo]:
    services = _list_units("system") + _list_units("user")
    services.sort(key=lambda item: (item.name.casefold(), item.scope))
    return services


def _base_command(scope: str) -> list[str]:
    command: list[str] = []
    if scope == "system" and os.geteuid() != 0:
        command.append("pkexec")
    command.append("systemctl")
    if scope == "user":
        command.append("--user")
    return command


def run_action(service: ServiceInfo, action: str) -> tuple[bool, str]:
    if action not in ("start", "stop", "restart", "enable", "disable"):
        raise ValueError("Acción no válida")
    command = _base_command(service.scope) + [action, service.name]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except FileNotFoundError:
        return False, "No se encontró systemctl o pkexec en el sistema."
    except subprocess.TimeoutExpired:
        return False, "La operación tardó demasiado. Inténtalo de nuevo."
    except OSError as error:
        return False, f"No se pudo ejecutar la operación: {error}"
    if result.returncode == 0:
        messages = {
            "start": "Servicio iniciado.",
            "stop": "Servicio detenido.",
            "restart": "Servicio reiniciado.",
            "enable": "Servicio habilitado al inicio.",
            "disable": "Servicio deshabilitado al inicio.",
        }
        return True, messages[action]
    message = (result.stderr or result.stdout or "").strip()
    if result.returncode in (126, 127):
        return False, "La operación se canceló o no se concedieron permisos de administrador."
    return False, message or "No se pudo completar la operación."


def service_journal(service: ServiceInfo, lines: int = 200) -> str:
    command = ["journalctl"]
    if service.scope == "user":
        command.append("--user")
    command += [
        "-u",
        service.name,
        "-n",
        str(lines),
        "--no-pager",
        "-o",
        "short-iso",
    ]
    output = _run(command, timeout=10)
    if output.strip():
        return output
    return "No hay registros disponibles o no tienes permisos para leerlos."


__all__ = ["ServiceInfo", "list_services", "run_action", "service_journal"]
