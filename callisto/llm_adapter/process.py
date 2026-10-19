"""Bounded, cancellable CLI subprocess transport (no shell, no credential reads)."""

import asyncio
import os
import signal
import subprocess
from dataclasses import dataclass

from callisto.llm_adapter.errors import CLIError
from callisto.llm_adapter.environment import cli_environment


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


async def _terminate(process):
    if os.name == "nt":
        # taskkill /T also terminates descendants; never terminate unrelated CLIs.
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/PID", str(process.pid), "/T", "/F",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=1)
        except TimeoutError:
            pass
        # The group can still have descendants even if the leader has exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await process.wait()


async def run_process(command, *, stdin: str, cwd: str, timeout: float, max_bytes=32_000_000,
                      provider: str | None = None):
    if timeout <= 0:
        raise ValueError("CLI timeout must be positive")
    options = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
    }
    try:
        process = await asyncio.create_subprocess_exec(
            *command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=cli_environment(provider), **options,
        )
    except OSError:
        raise CLIError("AI CLI could not be started; check its executable and installation") from None

    async def read_bounded(stream):
        chunks = []
        total = 0
        while chunk := await stream.read(65536):
            total += len(chunk)
            if total > max_bytes:
                raise CLIError("CLI output exceeded the configured size limit")
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")

    async def write_input():
        try:
            process.stdin.write(stdin.encode("utf-8"))
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            process.stdin.close()

    readers = [asyncio.create_task(read_bounded(process.stdout)),
               asyncio.create_task(read_bounded(process.stderr)),
               asyncio.create_task(write_input())]
    try:
        async with asyncio.timeout(timeout):
            stdout, stderr, _ = await asyncio.gather(*readers)
            await process.wait()
        return ProcessResult(process.returncode, stdout, stderr)
    except BaseException:
        await asyncio.shield(_terminate(process))
        for task in readers:
            task.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        raise
