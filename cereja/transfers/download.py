"""HTTP-to-filesystem transfers, separate from HTTP transport."""

import asyncio
from pathlib import Path

from cereja.http import AsyncClient, Client, HTTPStatusError
from cereja.http._core.disposition import _basename

from .models import DownloadResult, TransferProgress
from .sinks import AtomicFileSink


class _DownloadHTTPStatusError(HTTPStatusError, RuntimeError):
    """Typed download status error retaining legacy RuntimeError catches."""


def _raise_for_download_status(response, url):
    if response.status_code >= 400:
        raise _DownloadHTTPStatusError(
            f"HTTP {response.status_code} while downloading {url}",
            request=getattr(response, 'request', None),
            response=response,
        )


def _download_stream(client, url, timeout, headers):
    if headers is None:
        return client.stream("GET", url, timeout=timeout)
    return client.stream("GET", url, timeout=timeout, headers=headers)


async def _file_operation(operation, *args):
    """Finish an owned filesystem worker before propagating cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        await asyncio.wait((worker,))
    except asyncio.CancelledError:
        while not worker.done():
            try:
                await asyncio.wait((worker,))
            except asyncio.CancelledError:
                continue
        if not worker.cancelled():
            # Observe a late worker failure; cancellation still takes precedence.
            worker.exception()
        raise
    return worker.result()


def _total(headers):
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _validate_policy(max_bytes, overwrite):
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 1):
        raise ValueError('max_bytes must be a positive integer')
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be bool')


def _prepare_destination(destination, destination_dir, fallback_filename):
    if (destination is None) == (destination_dir is None):
        raise ValueError('Provide exactly one of destination or destination_dir')
    if destination_dir is not None:
        if not isinstance(fallback_filename, str):
            raise TypeError('fallback_filename must be a string')
        if _basename(fallback_filename) != fallback_filename:
            raise ValueError('fallback_filename must be a usable basename without path components')
        return Path(destination_dir)
    return Path(destination)


def download(url, destination=None, *, client=None, progress=None, chunk_size=65536, timeout=None,
             max_bytes=None, overwrite=True, before_commit=None, headers=None,
             destination_dir=None, fallback_filename='download.bin'):
    """Stream a GET response to an atomic file sink with optional request headers.

    max_bytes bounds received bytes; overwrite=False publishes without replacing
    an existing destination. A supplied client remains owned by the caller.
    Use destination_dir instead of destination to select the server's filename,
    or fallback_filename when no usable filename was supplied.
    HTTP error statuses raise HTTPStatusError, also catchable as RuntimeError
    for compatibility, with the request and closed streaming response attached.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    _validate_policy(max_bytes, overwrite)
    if before_commit is not None and not callable(before_commit):
        raise TypeError('before_commit must be callable')
    destination = _prepare_destination(destination, destination_dir, fallback_filename)
    owns_client = client is None
    client = client or Client()
    sink = None
    transferred = 0
    try:
        with _download_stream(client, url, timeout, headers) as response:
            _raise_for_download_status(response, url)
            total = _total(response.headers)
            if max_bytes is not None and total is not None and total < 0:
                raise ValueError('Negative response length')
            if max_bytes is not None and total is not None and total > max_bytes:
                raise ValueError('Download byte limit')
            if destination_dir is not None:
                destination = destination / (response.filename or fallback_filename)
            sink = AtomicFileSink(destination, overwrite=overwrite)
            handle = sink.open()
            for chunk in response.iter_bytes(chunk_size):
                if max_bytes is not None and transferred + len(chunk) > max_bytes:
                    raise ValueError('Download byte limit')
                handle.write(chunk)
                transferred += len(chunk)
                if progress:
                    progress(TransferProgress(transferred, total))
        if max_bytes is not None and total is not None and total != transferred:
            raise ValueError('Response length mismatch')
        if before_commit:
            before_commit()
        sink.commit()
        return DownloadResult(Path(destination), transferred, total, response.status_code)
    except BaseException:
        if sink is not None:
            sink.abort()
        raise
    finally:
        if owns_client:
            client.close()


async def async_download(url, destination=None, *, client=None, progress=None, chunk_size=65536, timeout=None,
                         max_bytes=None, overwrite=True, headers=None,
                         destination_dir=None, fallback_filename='download.bin'):
    """Async download with the same headers, byte limit, and overwrite policy.

    Filesystem operations run in worker threads. A supplied client remains owned
    by the caller; the destination is published only after a completed transfer.
    destination_dir selects the server's filename, with fallback_filename used
    when the response does not provide a usable name.
    HTTP error statuses raise HTTPStatusError, also catchable as RuntimeError
    for compatibility, with the request and closed streaming response attached.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    _validate_policy(max_bytes, overwrite)
    destination = _prepare_destination(destination, destination_dir, fallback_filename)
    owns_client = client is None
    client = client or AsyncClient()
    sink = None
    transferred = 0
    try:
        async with _download_stream(client, url, timeout, headers) as response:
            _raise_for_download_status(response, url)
            total = _total(response.headers)
            if max_bytes is not None and total is not None and total < 0:
                raise ValueError('Negative response length')
            if max_bytes is not None and total is not None and total > max_bytes:
                raise ValueError('Download byte limit')
            if destination_dir is not None:
                destination = destination / (response.filename or fallback_filename)
            sink = AtomicFileSink(destination, overwrite=overwrite)
            handle = await _file_operation(sink.open)
            async for chunk in response.aiter_bytes(chunk_size):
                if max_bytes is not None and transferred + len(chunk) > max_bytes:
                    raise ValueError('Download byte limit')
                await _file_operation(handle.write, chunk)
                transferred += len(chunk)
                if progress:
                    value = progress(TransferProgress(transferred, total))
                    if asyncio.iscoroutine(value):
                        await value
        if max_bytes is not None and total is not None and total != transferred:
            raise ValueError('Response length mismatch')
        await _file_operation(sink.commit)
        return DownloadResult(Path(destination), transferred, total, response.status_code)
    except BaseException:
        if sink is not None:
            await _file_operation(sink.abort)
        raise
    finally:
        if owns_client:
            await client.aclose()
