import os
import tempfile
import time
from pathlib import Path

import docker
from docker.types import Ulimit

from app.config import get_settings

settings = get_settings()


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated)"


def run_python_sync(
    code: str,
    stdin: str = "",
    timeout_sec: int | None = None,
) -> tuple[str | None, str | None, int | None, int, str]:
    timeout = timeout_sec or settings.execute_timeout_sec
    limit = settings.execute_output_limit
    start = time.time()

    try:
        client = docker.from_env()
    except Exception as e:
        return None, str(e), None, 0, "error"

    with tempfile.TemporaryDirectory() as tmpdir:
        main_py = Path(tmpdir) / "main.py"
        main_py.write_text(code, encoding="utf-8")

        try:
            container = client.containers.run(
                image="python:3.11-slim",
                command=["python", "/sandbox/main.py"],
                volumes={str(main_py): {"bind": "/sandbox/main.py", "mode": "ro"}},
                network_mode="none",
                read_only=True,
                tmpfs={"/tmp": "size=64m"},
                mem_limit="256m",
                memswap_limit="256m",
                pids_limit=64,
                nano_cpus=int(0.5 * 1e9),
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                user="65534:65534",
                ulimits=[Ulimit(name="fsize", soft=1024 * 1024, hard=1024 * 1024)],
                stdin_open=bool(stdin),
                detach=True,
                remove=False,
            )
        except Exception as e:
            return None, str(e), None, int((time.time() - start) * 1000), "error"

        if stdin:
            try:
                sock = container.attach_socket(params={"stdin": 1, "stream": 1})
                sock._sock.sendall(stdin.encode())
                sock.close()
            except Exception:
                pass

        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            container.remove(force=True)
            duration = int((time.time() - start) * 1000)
            if exit_code == 0:
                return _truncate(logs, limit), None, exit_code, duration, "done"
            return _truncate(logs, limit), _truncate(logs, limit), exit_code, duration, "done"
        except Exception:
            try:
                container.kill()
            except Exception:
                pass
            try:
                container.remove(force=True)
            except Exception:
                pass
            duration = int((time.time() - start) * 1000)
            return None, "Execution timeout", None, duration, "timeout"
