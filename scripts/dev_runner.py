from __future__ import annotations

import asyncio
import os
import signal
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence


@dataclass(frozen=True)
class ServiceCommand:
    name: str
    command: Sequence[str]
    cwd: Path
    env: Mapping[str, str] | None = None


class DevProcessManager:
    def __init__(self, services: Iterable[ServiceCommand]) -> None:
        self._services = list(services)
        self._processes: list[tuple[ServiceCommand, asyncio.subprocess.Process]] = []
        self._stream_tasks: list[asyncio.Task[None]] = []
        self._wait_tasks: list[asyncio.Task[tuple[str, int]]] = []

    async def run(self) -> None:
        try:
            await self._start_all()
            await self._monitor()
        except KeyboardInterrupt:
            print("\nReceived Ctrl+C; shutting down...")
        except FileNotFoundError as exc:
            missing = exc.filename or "executable"
            print(
                f"\nCould not start '{missing}'. Make sure the dependency is installed and on your PATH."
            )
        finally:
            await self._shutdown()

    async def _start_all(self) -> None:
        for service in self._services:
            process = await self._launch(service)
            self._processes.append((service, process))
            if process.stdout:
                self._stream_tasks.append(
                    asyncio.create_task(self._forward_stream(service.name, process.stdout))
                )
            if process.stderr:
                self._stream_tasks.append(
                    asyncio.create_task(
                        self._forward_stream(service.name, process.stderr, is_error=True)
                    )
                )
            self._wait_tasks.append(
                asyncio.create_task(self._wait_for_exit(service, process))
            )

    async def _monitor(self) -> None:
        if not self._wait_tasks:
            return

        done, pending = await asyncio.wait(
            self._wait_tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

        if done:
            service_name, return_code = await done.pop()
            if return_code == 0:
                print(f"\n{service_name} exited cleanly; stopping other services...")
            else:
                print(
                    f"\n{service_name} exited with code {return_code}; stopping other services..."
                )

    async def _shutdown(self) -> None:
        for task in self._wait_tasks:
            task.cancel()

        for service, process in self._processes:
            if process.returncode is None:
                self._terminate_process(service.name, process)

        for _, process in self._processes:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=10)

        for task in self._stream_tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _forward_stream(
        self, name: str, stream: asyncio.StreamReader, *, is_error: bool = False
    ) -> None:
        prefix = f"[{name}] "
        while True:
            line = await stream.readline()
            if not line:
                break

            text = line.decode(errors="ignore").rstrip()
            if is_error:
                print(f"{prefix}{text}", file=sys.stderr)
            else:
                print(f"{prefix}{text}")

    async def _wait_for_exit(
        self, service: ServiceCommand, process: asyncio.subprocess.Process
    ) -> tuple[str, int]:
        return_code = await process.wait()
        return service.name, return_code

    async def _launch(
        self, service: ServiceCommand
    ) -> asyncio.subprocess.Process:
        env: MutableMapping[str, str] = os.environ.copy()
        if service.env:
            env.update({key: value for key, value in service.env.items() if value is not None})

        try:
            return await asyncio.create_subprocess_exec(
                *service.command,
                cwd=str(service.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(service.command[0]) from exc

    def _terminate_process(
        self, name: str, process: asyncio.subprocess.Process
    ) -> None:
        if sys.platform.startswith("win"):
            process.terminate()
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                if process.returncode is None:
                    process.send_signal(sig)


def build_services(root: Path) -> list[ServiceCommand]:
    python = sys.executable
    backend_dir = root / "backend"
    frontend_dir = root / "frontend"

    default_token = os.environ.get("SERVICE_TOKEN", "dev-service-token")
    python_env = {"SERVICE_TOKEN": default_token}

    frontend_api_defaults = {
        "VITE_API_MAIN": "http://localhost:8000",
        "VITE_API_PRICE": "http://localhost:8101",
        "VITE_API_WEATHER": "http://localhost:8102",
        "VITE_API_BATTERY": "http://localhost:8103",
    }
    frontend_env = {
        key: os.environ.get(key, value) for key, value in frontend_api_defaults.items()
    }

    return [
        ServiceCommand(
            name="backend",
            command=[
                python,
                "-m",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=backend_dir,
            env=python_env,
        ),
        ServiceCommand(
            name="pricing",
            command=[
                python,
                "-m",
                "uvicorn",
                "pricing_service.app.main:app",
                "--reload",
                "--port",
                "8101",
            ],
            cwd=root,
            env=python_env,
        ),
        ServiceCommand(
            name="weather",
            command=[
                python,
                "-m",
                "uvicorn",
                "weather_service.app.main:app",
                "--reload",
                "--port",
                "8102",
            ],
            cwd=root,
            env=python_env,
        ),
        ServiceCommand(
            name="battery",
            command=[
                python,
                "-m",
                "uvicorn",
                "battery_service.app.main:app",
                "--reload",
                "--port",
                "8103",
            ],
            cwd=root,
            env=python_env,
        ),
        ServiceCommand(
            name="frontend",
            command=_npm_command(),
            cwd=frontend_dir,
            env=frontend_env,
        ),
    ]


def _npm_command() -> list[str]:
    base_cmd = "npm.cmd" if sys.platform.startswith("win") else "npm"
    return [base_cmd, "run", "dev", "--", "--host"]


async def _async_main() -> None:
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    root = Path(__file__).resolve().parents[1]
    backend_dir = root / "backend"
    await reset_database_file(backend_dir / "bikeshare.db")
    await seed_database(sys.executable, backend_dir)
    services = build_services(root)
    manager = DevProcessManager(services)
    await manager.run()


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        # asyncio.run already handles KeyboardInterrupt, but guard in case.
        pass


async def seed_database(python: str, backend_dir: Path) -> None:
    print("Seeding database (python -m app.seed)...")
    process = await asyncio.create_subprocess_exec(
        python,
        "-m",
        "app.seed",
        cwd=str(backend_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )

    stdout, stderr = await process.communicate()
    if stdout:
        print(stdout.decode(errors="ignore"), end="")
    if stderr:
        print(stderr.decode(errors="ignore"), end="", file=sys.stderr)

    if process.returncode != 0:
        raise SystemExit(
            f"Seeding failed with exit code {process.returncode}. Fix this and rerun the launcher."
        )


async def reset_database_file(db_path: Path) -> None:
    if db_path.exists():
        print(f"Removing existing database at {db_path}...")
        try:
            db_path.unlink()
        except Exception as exc:
            raise SystemExit(f"Failed to remove existing database {db_path}: {exc}") from exc


if __name__ == "__main__":
    main()
