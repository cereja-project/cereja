"""Controlled local benchmark for Cereja HTTP clients.

This is evidence tooling, not a correctness gate. Run from the repository root:
    python benchmarks/http.py --requests 200 --concurrency 20
"""

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import statistics
import threading
import time

from cereja.http import AsyncClient, Client


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/"


def sync_benchmark(url, count):
    samples = []
    started = time.perf_counter()
    with Client() as client:
        for _ in range(count):
            one = time.perf_counter()
            client.get(url)
            samples.append(time.perf_counter() - one)
    return time.perf_counter() - started, samples


async def async_benchmark(url, count, concurrency):
    semaphore = asyncio.Semaphore(concurrency)
    samples = []
    async with AsyncClient(max_connections=concurrency) as client:
        async def one():
            async with semaphore:
                started = time.perf_counter()
                await client.get(url)
                samples.append(time.perf_counter() - started)
        started = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(count)))
    return time.perf_counter() - started, samples


def report(name, total, samples):
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(f"{name}: total={total:.4f}s throughput={len(samples) / total:.1f}/s "
          f"median={statistics.median(samples) * 1000:.3f}ms p95={p95 * 1000:.3f}ms")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    server, thread, url = start_server()
    try:
        report("sync", *sync_benchmark(url, args.requests))
        report("async", *asyncio.run(async_benchmark(url, args.requests, args.concurrency)))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
