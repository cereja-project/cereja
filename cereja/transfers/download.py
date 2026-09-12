"""HTTP-to-filesystem transfers, separate from HTTP transport."""

import asyncio
from pathlib import Path

from cereja.http import AsyncClient, Client

from .models import DownloadResult, TransferProgress
from .sinks import AtomicFileSink


def _total(headers):
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def download(url, destination, *, client=None, progress=None, chunk_size=65536, timeout=None):
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    owns_client = client is None
    client = client or Client()
    sink = AtomicFileSink(destination)
    transferred = 0
    try:
        with client.stream("GET", url, timeout=timeout) as response:
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code} while downloading {url}")
            total = _total(response.headers)
            handle = sink.open()
            for chunk in response.iter_bytes(chunk_size):
                handle.write(chunk)
                transferred += len(chunk)
                if progress:
                    progress(TransferProgress(transferred, total))
        sink.commit()
        return DownloadResult(Path(destination), transferred, total, response.status_code)
    except BaseException:
        sink.abort()
        raise
    finally:
        if owns_client:
            client.close()


async def async_download(url, destination, *, client=None, progress=None, chunk_size=65536, timeout=None):
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    owns_client = client is None
    client = client or AsyncClient()
    sink = AtomicFileSink(destination)
    transferred = 0
    try:
        async with client.stream("GET", url, timeout=timeout) as response:
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code} while downloading {url}")
            total = _total(response.headers)
            handle = await asyncio.to_thread(sink.open)
            async for chunk in response.aiter_bytes(chunk_size):
                await asyncio.to_thread(handle.write, chunk)
                transferred += len(chunk)
                if progress:
                    value = progress(TransferProgress(transferred, total))
                    if asyncio.iscoroutine(value):
                        await value
        await asyncio.to_thread(sink.commit)
        return DownloadResult(Path(destination), transferred, total, response.status_code)
    except BaseException:
        await asyncio.to_thread(sink.abort)
        raise
    finally:
        if owns_client:
            await client.aclose()
