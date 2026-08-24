"""Controlled execution for administrator-configured shell actions."""

from __future__ import annotations

from dataclasses import dataclass
import os
import signal
import subprocess
import tempfile


@dataclass(frozen=True)
class ScriptExecutionResult:
    exit_code: int
    output: str


def _script_environment() -> dict[str, str]:
    allowed_names = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TZ')
    environment = {
        name: value
        for name in allowed_names
        if (value := os.environ.get(name))
    }
    environment['NUTIFY_SCRIPT_ACTION'] = '1'
    return environment


def run_shell_script(script_body: str, timeout_seconds: int = 30) -> ScriptExecutionResult:
    """Execute one script and terminate its process group on timeout."""
    script_path = None
    process = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.sh', encoding='utf-8', delete=False) as handle:
            script_path = handle.name
            handle.write(str(script_body or ''))
        os.chmod(script_path, 0o700)

        process = subprocess.Popen(
            ['/bin/sh', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=_script_environment(),
        )
        try:
            stdout, stderr = process.communicate(timeout=max(1, int(timeout_seconds)))
            exit_code = int(process.returncode or 0)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            exit_code = 124
            stderr = f"{stderr or ''}\nScript timed out after {timeout_seconds} seconds."

        output = f"{stdout or ''}\n{stderr or ''}".strip()[:2000]
        return ScriptExecutionResult(exit_code=exit_code, output=output)
    except Exception as exc:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        return ScriptExecutionResult(exit_code=1, output=str(exc)[:2000])
    finally:
        if script_path and os.path.isfile(script_path):
            try:
                os.remove(script_path)
            except OSError:
                pass
