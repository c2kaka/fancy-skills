#!/usr/bin/env python3
"""Secure operation state and cross-process locking."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class StateError(RuntimeError):
    """Raised when operation state is unsafe or inconsistent."""


class OperationAlreadyRunningError(StateError):
    """Raised when another process holds the same operation lock."""


def ensure_state_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def operation_path(state_dir: Path, operation_id: str) -> Path:
    if not operation_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
        for character in operation_id
    ):
        raise StateError("operation ID 只能包含小写字母、数字和连字符。")
    return ensure_state_dir(state_dir) / f"{operation_id}.json"


def read_state(state_dir: Path, operation_id: str) -> dict[str, object] | None:
    path = operation_path(state_dir, operation_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"无法读取 operation state：{operation_id}: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"operation state 格式无效：{operation_id}")
    return data


def write_state(state_dir: Path, operation_id: str, data: dict[str, object]) -> Path:
    destination = operation_path(state_dir, operation_id)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{operation_id}.", dir=destination.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


@contextmanager
def operation_lock(state_dir: Path, operation_id: str) -> Iterator[None]:
    lock_path = ensure_state_dir(state_dir) / f"{operation_id}.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OperationAlreadyRunningError(
                f"OperationAlreadyRunning: {operation_id}"
            ) from exc
        os.ftruncate(descriptor, 0)
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.fsync(descriptor)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def cleanup_state(state_dir: Path, operation_id: str) -> None:
    state = read_state(state_dir, operation_id)
    if state is None:
        raise StateError(f"找不到 operation：{operation_id}")
    if state.get("status") != "verified":
        raise StateError(
            "只能清理 verified operation；partial、unknown 或 unverified 状态必须保留。"
        )
    operation_path(state_dir, operation_id).unlink()
    (ensure_state_dir(state_dir) / f"{operation_id}.lock").unlink(missing_ok=True)
