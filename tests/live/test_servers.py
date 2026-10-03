"""The lifespan contract against real ASGI servers, each run as a process.

Run by ``nox -s servers``; the other sessions do not collect this directory.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

PROJECT = Path(__file__).parent
TIMEOUT = 20
SERVERS = {
    "uvicorn": [
        "uvicorn",
        "project.asgi:application",
        "--port",
        "{port}",
        "--lifespan",
        "on",
    ],
    "granian": [
        "granian",
        "--interface",
        "asgi",
        "--port",
        "{port}",
        "project.asgi:application",
    ],
    "hypercorn": [
        "hypercorn",
        "project.asgi:application",
        "--bind",
        "127.0.0.1:{port}",
    ],
}
# Observed exit codes. Uvicorn raises SIGTERM again after a graceful shutdown
# (its supervisor of several workers exits with 0); Hypercorn reports a failed
# startup and exits with 0.
SHUTDOWN_EXIT_CODES = {"uvicorn": -signal.SIGTERM, "granian": 0, "hypercorn": 0}
STARTUP_FAILURE_EXIT_CODES = {"uvicorn": 3, "granian": 1, "hypercorn": 0}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, name, directory, *arguments, fail=False):
        self.port = free_port()
        self.log = directory / "lifespan.log"
        self.log.touch()
        self.output = directory / "output.txt"
        command = [part.format(port=self.port) for part in SERVERS[name]]
        environment = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "project.settings",
            "PYTHONPATH": str(PROJECT),
            "LIFESPAN_LOG": str(self.log),
            "LIFESPAN_FAIL": "1" if fail else "0",
        }
        with self.output.open("wb") as output:
            self.process = subprocess.Popen(
                [sys.executable, "-m", *command, *arguments],
                cwd=PROJECT,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
            )

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/state/"

    def events(self):
        return self.log.read_text().splitlines()

    def fail(self, reason):
        pytest.fail(f"{reason}\n--- server output ---\n{self.output.read_text()}")

    def get(self):
        response = httpx.get(self.url, timeout=TIMEOUT)
        assert response.status_code == 200, response.text
        return response.json()

    def wait_until(self, condition, reason):
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail(f"The server exited with {self.process.returncode}.")
            if condition():
                return
            time.sleep(0.05)
        self.fail(f"Timed out: {reason}.")

    def wait_ready(self):
        def answers():
            try:
                httpx.get(self.url, timeout=1)
            except httpx.TransportError:
                return False
            return True

        self.wait_until(answers, "the server did not answer")

    def wait_exit(self):
        try:
            return self.process.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            self.fail("The server did not exit.")

    def stop(self):
        self.process.send_signal(signal.SIGTERM)
        return self.wait_exit()


@pytest.fixture
def serve(tmp_path):
    servers = []

    def start(name, *arguments, fail=False):
        directory = tmp_path / str(len(servers))
        directory.mkdir()
        server = Server(name, directory, *arguments, fail=fail)
        servers.append(server)
        return server

    yield start
    for server in servers:
        if server.process.poll() is None:
            server.process.kill()
            server.process.wait()


@pytest.mark.parametrize("name", SERVERS)
def test_receivers_run_after_the_context_is_entered(serve, name):
    server = serve(name)
    server.wait_ready()
    pid = server.get()["pid"]
    assert server.events() == [f"opened {pid}", "signal startup", "signal startup"]
    assert server.stop() == SHUTDOWN_EXIT_CODES[name]


@pytest.mark.parametrize("name", SERVERS)
def test_requests_share_the_lifespan_resource(serve, name):
    server = serve(name)
    server.wait_ready()
    first, second = server.get(), server.get()
    assert first["token"] == second["token"]
    assert server.stop() == SHUTDOWN_EXIT_CODES[name]


@pytest.mark.parametrize("name", SERVERS)
def test_shutdown_receivers_run_before_the_context_is_closed(serve, name):
    server = serve(name)
    server.wait_ready()
    pid = server.get()["pid"]
    assert server.stop() == SHUTDOWN_EXIT_CODES[name]
    assert server.events()[-3:] == [
        "signal shutdown",
        "signal shutdown",
        f"closed {pid}",
    ]


@pytest.mark.parametrize("name", SERVERS)
def test_failed_startup_stops_the_server(serve, name):
    server = serve(name, fail=True)
    assert server.wait_exit() == STARTUP_FAILURE_EXIT_CODES[name]
    assert "startup failed on purpose" in server.output.read_text()
    assert server.events() == []


def test_each_worker_enters_its_own_context(serve):
    server = serve("uvicorn", "--workers", "2")

    def opened():
        return [event for event in server.events() if event.startswith("opened ")]

    server.wait_until(lambda: len(opened()) == 2, "two workers did not start")
    pids = {event.removeprefix("opened ") for event in opened()}
    assert len(pids) == 2
    assert server.stop() == 0
    closed = {
        event.removeprefix("closed ")
        for event in server.events()
        if event.startswith("closed ")
    }
    assert closed == pids
