"""Sesiones de usuario activas y consumo agregado."""

from __future__ import annotations

import json
import os
import pwd
import subprocess
from dataclasses import dataclass, field

import psutil

from .processes import ProcessInfo


@dataclass(slots=True)
class SessionInfo:
    session_id: str
    uid: int
    username: str
    seat: str = ""
    tty: str = ""
    session_type: str = ""
    session_class: str = "user"
    state: str = ""
    remote: bool = False
    active: bool = False
    display: str = ""
    leader: int = 0
    started: float = 0.0
    is_current: bool = False
    cpu_percent: float = 0.0
    memory_rss: int = 0
    process_count: int = 0
    pids: list[int] = field(default_factory=list)

    @property
    def type_text(self) -> str:
        mapping = {
            "wayland": "Wayland",
            "x11": "X11",
            "tty": "Terminal",
            "mir": "Mir",
            "unspecified": "Sistema",
        }
        return mapping.get(self.session_type.lower(), self.session_type or "Sistema")

    @property
    def state_text(self) -> str:
        mapping = {
            "active": "Activa",
            "online": "Conectada",
            "closing": "Cerrando",
            "lingering": "En segundo plano",
        }
        return mapping.get(self.state.lower(), self.state or "Activa")


def _run(args: list[str], timeout: float = 4.0) -> str:
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


def _session_properties(session_id: str) -> dict[str, str]:
    output = _run(
        [
            "loginctl",
            "show-session",
            session_id,
            "-p",
            "Type",
            "-p",
            "State",
            "-p",
            "Remote",
            "-p",
            "Active",
            "-p",
            "TTY",
            "-p",
            "Display",
            "-p",
            "Class",
        ]
    )
    properties: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
    return properties


def _current_session_id(sessions: list[dict]) -> str:
    env_id = os.environ.get("XDG_SESSION_ID", "")
    if env_id:
        return env_id
    ancestors: set[int] = set()
    pid = os.getpid()
    for _ in range(40):
        ancestors.add(pid)
        try:
            pid = psutil.Process(pid).ppid()
        except psutil.Error:
            break
        if pid <= 1:
            break
    for session in sessions:
        leader = session.get("leader")
        if leader in ancestors:
            return str(session.get("session", ""))
    return ""


def _sessions_from_psutil() -> list[SessionInfo]:
    sessions: list[SessionInfo] = []
    seen: set[tuple[str, str, float]] = set()
    current_user = os.environ.get("USER", "")
    for user in psutil.users():
        key = (user.name, user.terminal or "", float(user.started))
        if key in seen:
            continue
        seen.add(key)
        try:
            uid = pwd.getpwnam(user.name).pw_uid
        except KeyError:
            uid = 0
        sessions.append(
            SessionInfo(
                session_id="",
                uid=uid,
                username=user.name,
                seat=user.terminal or "",
                tty=user.terminal or "",
                session_type="tty"
                if user.terminal and "tty" in user.terminal
                else "wayland",
                state="active" if user.pid else "",
                active=bool(user.pid),
                leader=user.pid or 0,
                started=float(user.started or 0.0),
                is_current=user.name == current_user and bool(user.pid),
            )
        )
    return sessions


def list_sessions(processes: list[ProcessInfo] | None = None) -> list[SessionInfo]:
    raw_output = _run(["loginctl", "list-sessions", "--json=short", "--no-pager"])
    raw_sessions: list[dict] = []
    if raw_output.strip():
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, list):
                raw_sessions = [item for item in parsed if isinstance(item, dict)]
        except ValueError:
            raw_sessions = []

    sessions: list[SessionInfo] = []
    if raw_sessions:
        current_id = _current_session_id(raw_sessions)
        for item in raw_sessions:
            session_id = str(item.get("session", ""))
            session_class = str(item.get("class", "user"))
            if session_class == "manager":
                continue
            properties = _session_properties(session_id)
            leader = int(item.get("leader") or 0)
            started = 0.0
            if leader:
                try:
                    started = psutil.Process(leader).create_time()
                except psutil.Error:
                    started = 0.0
            sessions.append(
                SessionInfo(
                    session_id=session_id,
                    uid=int(item.get("uid") or 0),
                    username=str(item.get("user") or "?"),
                    seat=str(item.get("seat") or ""),
                    tty=str(item.get("tty") or properties.get("TTY", "")),
                    session_type=properties.get("Type", ""),
                    session_class=session_class,
                    state=properties.get("State", ""),
                    remote=properties.get("Remote", "no").lower() == "yes",
                    active=properties.get("Active", "no").lower() == "yes",
                    display=properties.get("Display", ""),
                    leader=leader,
                    started=started,
                    is_current=bool(current_id) and session_id == current_id,
                )
            )
    else:
        sessions = _sessions_from_psutil()

    if not any(session.is_current for session in sessions):
        try:
            current_user = pwd.getpwuid(os.getuid()).pw_name
        except KeyError:
            current_user = os.environ.get("USER", "")
        for session in sessions:
            if session.username == current_user and session.session_class == "user":
                session.is_current = True

    _aggregate_usage(sessions, processes or [])
    sessions.sort(key=lambda item: (not item.is_current, item.username.casefold(), item.session_id))
    return sessions


def _aggregate_usage(sessions: list[SessionInfo], processes: list[ProcessInfo]) -> None:
    by_uid: dict[int, list[ProcessInfo]] = {}
    by_user: dict[str, list[ProcessInfo]] = {}
    for process in processes:
        by_uid.setdefault(process.uid, []).append(process)
        by_user.setdefault(process.username, []).append(process)
    for session in sessions:
        items = by_uid.get(session.uid) or by_user.get(session.username) or []
        session.cpu_percent = round(sum(item.cpu_percent for item in items), 1)
        session.memory_rss = sum(item.memory_rss for item in items)
        session.process_count = len(items)
        session.pids = [item.pid for item in items]


def terminate_session(session: SessionInfo) -> None:
    if not session.session_id:
        raise RuntimeError("No se pudo identificar la sesión.")
    result = subprocess.run(
        ["loginctl", "terminate-session", session.session_id],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or "No se pudo cerrar la sesión.")


__all__ = ["SessionInfo", "list_sessions", "terminate_session"]
