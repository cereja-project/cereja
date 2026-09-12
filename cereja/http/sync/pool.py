"""Bounded synchronous connection pool."""

import threading
import time

from ..errors import PoolTimeout


class ConnectionPool:
    def __init__(self, max_connections=20):
        if max_connections < 1:
            raise ValueError("max_connections must be >= 1")
        self.max_connections = int(max_connections)
        self._condition = threading.Condition()
        self._idle = {}
        self._total = 0
        self._closed = False

    def acquire(self, key, factory, timeout):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while True:
                if self._closed:
                    raise RuntimeError("Connection pool is closed")
                idle = self._idle.get(key)
                while idle:
                    connection = idle.pop()
                    if getattr(connection, "sock", None) is not None:
                        return connection
                    self._total -= 1
                if self._total < self.max_connections:
                    self._total += 1
                    break

                # A global connection limit must not deadlock requests to a new
                # origin while another origin owns idle capacity. Evict one
                # idle connection before waiting for an in-use connection.
                victim = None
                for values in self._idle.values():
                    if values:
                        victim = values.pop()
                        break
                if victim is not None:
                    self._total -= 1
                    victim.close()
                    self._total += 1
                    break

                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise PoolTimeout("Timed out waiting for an HTTP connection")
                self._condition.wait(remaining)
        try:
            return factory()
        except BaseException:
            with self._condition:
                self._total -= 1
                self._condition.notify()
            raise

    def release(self, key, connection):
        with self._condition:
            if self._closed or getattr(connection, "sock", None) is None:
                try:
                    connection.close()
                finally:
                    self._total -= 1
                    self._condition.notify()
                return
            self._idle.setdefault(key, []).append(connection)
            self._condition.notify()

    def discard(self, connection):
        try:
            connection.close()
        finally:
            with self._condition:
                self._total -= 1
                self._condition.notify()

    def close(self):
        with self._condition:
            if self._closed:
                return
            self._closed = True
            connections = [conn for values in self._idle.values() for conn in values]
            self._idle.clear()
            self._total -= len(connections)
            self._condition.notify_all()
        for connection in connections:
            connection.close()
