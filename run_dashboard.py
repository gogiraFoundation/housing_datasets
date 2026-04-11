#!/usr/bin/env python3
"""Start the Streamlit dashboard and monitor it (logs + optional HTTP health checks, auto-restart)."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _streamlit_cmd(app: Path, host: str, port: int, headless: bool) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app.resolve()),
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]
    if headless:
        cmd.append("--server.headless")
        cmd.append("true")
    return cmd


def _forward_logs(stream, prefix: str) -> None:
    for line in iter(stream.readline, ""):
        if not line:
            break
        print(f"{prefix}{line}", end="", flush=True)
    stream.close()


def _health_url(host: str, port: int) -> str:
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::", "[::]") else host
    if connect_host == "localhost":
        connect_host = "127.0.0.1"
    return f"http://{connect_host}:{port}/"


def _check_health(url: str, timeout: float) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main() -> int:
    root = _repo_root()
    p = argparse.ArgumentParser(
        description="Run and monitor the Streamlit dashboard (see app.py).",
    )
    p.add_argument(
        "--app",
        type=Path,
        default=root / "app.py",
        help="Path to the Streamlit app (default: app.py next to this script).",
    )
    p.add_argument("--host", default="localhost", help="Streamlit --server.address (default: localhost).")
    p.add_argument("--port", type=int, default=8501, help="Streamlit --server.port (default: 8501).")
    p.add_argument(
        "--headless",
        action="store_true",
        help="Pass --server.headless true (typical for servers without a browser).",
    )
    p.add_argument(
        "--restart",
        action="store_true",
        help="Restart the process if it exits or fails repeated health checks.",
    )
    p.add_argument(
        "--max-restarts",
        type=int,
        default=50,
        help="Maximum restart attempts when --restart is set (default: 50).",
    )
    p.add_argument(
        "--health-interval",
        type=float,
        default=30.0,
        help="Seconds between HTTP health checks to the app root; 0 disables (default: 30).",
    )
    p.add_argument(
        "--health-timeout",
        type=float,
        default=5.0,
        help="HTTP timeout per health check in seconds (default: 5).",
    )
    p.add_argument(
        "--unhealthy-threshold",
        type=int,
        default=3,
        help="Consecutive failed health checks before treating the server as dead (default: 3).",
    )
    args = p.parse_args()

    app = args.app if args.app.is_absolute() else root / args.app
    if not app.is_file():
        print(f"error: app not found: {app}", file=sys.stderr)
        return 1

    restarts = 0
    stop = threading.Event()

    def handle_signal(signum: int, frame) -> None:  # noqa: ARG001
        stop.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while not stop.is_set():
        cmd = _streamlit_cmd(app, args.host, args.port, args.headless)
        print(f"[dashboard] starting: {' '.join(cmd)}", flush=True)
        proc = subprocess.Popen(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        out_t = threading.Thread(target=_forward_logs, args=(proc.stdout, "[streamlit] "), daemon=True)
        out_t.start()

        health_url = _health_url(args.host, args.port)
        consecutive_failures = 0
        seen_ok = False

        while proc.poll() is None and not stop.is_set():
            if args.health_interval <= 0:
                time.sleep(0.5)
                continue
            time.sleep(args.health_interval)
            if stop.is_set():
                break
            ok = _check_health(health_url, args.health_timeout)
            if ok:
                seen_ok = True
                consecutive_failures = 0
                print(f"[dashboard] health ok {health_url}", flush=True)
            else:
                if not seen_ok:
                    print(f"[dashboard] health pending (startup) {health_url}", flush=True)
                    continue
                consecutive_failures += 1
                print(
                    f"[dashboard] health fail ({consecutive_failures}/{args.unhealthy_threshold}) {health_url}",
                    flush=True,
                )
                if consecutive_failures >= args.unhealthy_threshold and args.restart:
                    print("[dashboard] too many health failures; stopping process for restart", flush=True)
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break

        code = proc.poll()
        if code is None and stop.is_set():
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            print("[dashboard] stopped", flush=True)
            return 0

        if code is not None:
            print(f"[dashboard] process exited with code {code}", flush=True)

        if stop.is_set():
            return 0

        if not args.restart:
            return code if code is not None else 1

        restarts += 1
        if restarts > args.max_restarts:
            print(f"[dashboard] max restarts ({args.max_restarts}) reached; exiting", flush=True)
            return 1
        print(f"[dashboard] restarting ({restarts}/{args.max_restarts}) in 2s...", flush=True)
        time.sleep(2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
