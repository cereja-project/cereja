"""Bounded asyncio connection pool."""

import asyncio

from ..errors import PoolTimeout


class AsyncConnectionPool:
    def __init__(self, max_connections=20):
        if max_connections < 1:
            raise ValueError("max_connections must be >= 1")
        self.max_connections = int(max_connections)
        self._condition = asyncio.Condition()
        self._idle = {}
        self._total = 0
        self._closed = False

    async def acquire(self, key, factory, timeout):
        async def reserve():
            async with self._condition:
                while True:
                    if self._closed:
                        raise RuntimeError("Connection pool is closed")
                    idle = self._idle.get(key)
                    while idle:
                        connection = idle.pop()
                        if not connection.writer.is_closing():
                            return connection, False
                        self._total -= 1
                    if self._total < self.max_connections:
                        self._total += 1
                        return None, True
                    victim = None
                    for values in self._idle.values():
                        if values:
                            victim = values.pop()
                            break
                    if victim is not None:
                        self._total -= 1
                        victim.writer.close()
                        self._total += 1
                        return None, True
                    await self._condition.wait()

        try:
            if timeout is None:
                connection, create = await reserve()
            else:
                async with asyncio.timeout(timeout):
                    connection, create = await reserve()
        except TimeoutError as exc:
            raise PoolTimeout("Timed out waiting for an HTTP connection") from exc
        if not create:
            return connection
        try:
            return await factory()
        except BaseException:
            async with self._condition:
                self._total -= 1
                self._condition.notify()
            raise

    async def release(self, key, connection):
        async with self._condition:
            if self._closed or connection.writer.is_closing():
                self._total -= 1
                connection.writer.close()
            else:
                self._idle.setdefault(key, []).append(connection)
            self._condition.notify()

    async def discard(self, connection):
        connection.writer.close()
        try:
            await connection.writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        async with self._condition:
            self._total -= 1
            self._condition.notify()

    async def close(self):
        async with self._condition:
            if self._closed:
                return
            self._closed = True
            connections = [conn for values in self._idle.values() for conn in values]
            self._idle.clear()
            self._total -= len(connections)
            self._condition.notify_all()
        for connection in connections:
            connection.writer.close()
        await asyncio.gather(*(conn.writer.wait_closed() for conn in connections), return_exceptions=True)
