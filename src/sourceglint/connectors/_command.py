"""Narrow, shell-free command boundary for optional local source tools."""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Sequence

from ..deadline import limit_timeout


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run_command(command: Sequence[str], timeout: float) -> CommandResult:
    """Run an argv sequence without a shell and capture bounded text output."""
    try:
        timeout = limit_timeout(timeout)
    except TimeoutError as exc:
        raise subprocess.TimeoutExpired(command, timeout) from exc
    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


__all__ = ["CommandResult", "run_command"]
