import asyncio
import os
import sys
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPToolClient:
    """通过 stdio 子进程连接 app/mcp/server.py 的真实 MCP 客户端。

    Agent 层都是同步代码，而 MCP SDK 是 asyncio 原生的，所以这里起一个
    专属后台线程跑 event loop。stdio_client/ClientSession 的 async with
    必须在同一个 task 里进入和退出（anyio 的 cancel scope 有 task 亲和性），
    所以整个连接生命周期由一个长期运行的 _runner 协程持有，call_tool 通过
    一个 asyncio.Queue 把请求丢给它，再用 concurrent.futures.Future 把结果
    带回调用方所在的线程。
    """

    def __init__(
        self,
        tickets_file: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        env = dict(os.environ)
        if tickets_file is not None:
            env["TICKETS_FILE"] = str(tickets_file)
        if env_overrides:
            env.update(env_overrides)

        self._params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server"],
            env=env,
        )

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

        self._started = False
        self._queue: asyncio.Queue | None = None
        self._runner_future: Future | None = None

    def _ensure_started(self) -> None:
        if self._started:
            return

        self._started = True
        ready = threading.Event()
        start_error: dict[str, BaseException] = {}

        async def _runner() -> None:
            self._queue = asyncio.Queue()
            try:
                async with stdio_client(self._params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        ready.set()

                        while True:
                            item = await self._queue.get()
                            if item is None:
                                break

                            name, arguments, result_future = item
                            try:
                                result = await session.call_tool(name, arguments)
                                result_future.set_result(result)
                            except BaseException as exc:  # noqa: BLE001
                                result_future.set_exception(exc)
            except BaseException as exc:  # noqa: BLE001
                start_error["error"] = exc
                ready.set()

        self._runner_future = asyncio.run_coroutine_threadsafe(_runner(), self._loop)
        ready.wait(timeout=10)

        if "error" in start_error:
            raise start_error["error"]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self._ensure_started()

        result_future: Future = Future()
        asyncio.run_coroutine_threadsafe(
            self._queue.put((name, arguments, result_future)), self._loop
        ).result()

        call_result = result_future.result()

        if call_result.isError:
            message = (
                call_result.content[0].text if call_result.content else f"MCP tool '{name}' failed"
            )
            raise RuntimeError(message)

        return call_result.structuredContent

    def close(self) -> None:
        if self._started:
            asyncio.run_coroutine_threadsafe(self._queue.put(None), self._loop).result()
            self._runner_future.result(timeout=5)

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()
