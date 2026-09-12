import contextlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen_connections = set()

    def log_message(self, *args):
        pass

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(size) if size else b""

    def _send(self, status, body=b"", headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        if not any(name.lower() == "content-length" for name, _ in headers):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
            self.wfile.flush()

    def do_HEAD(self):
        self._send(200, b"hello")

    def do_GET(self):
        type(self).seen_connections.add(self.client_address[1])
        path = self.path.split("?", 1)[0]
        if path == "/fixed":
            self._send(200, b"hello", [("Content-Type", "text/plain; charset=utf-8")])
        elif path == "/json":
            self._send(200, b'{"ok":true}', [("Content-Type", "application/json")])
        elif path == "/large":
            self._send(200, b"x" * 65536)
        elif path == "/chunked":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for chunk in (b"abc", b"defg"):
                self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
            self.wfile.write(b"0\r\nX-Trailer: yes\r\n\r\n")
            self.wfile.flush()
        elif path == "/close":
            self.send_response(200)
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"bye")
            self.wfile.flush()
            self.close_connection = True
        elif path == "/redirect":
            self._send(302, b"", [("Location", "/fixed")])
        elif path == "/loop":
            self._send(302, b"", [("Location", "/loop")])
        elif path == "/slow":
            self.send_response(200)
            self.send_header("Content-Length", "4")
            self.end_headers()
            time.sleep(0.25)
            self.wfile.write(b"slow")
            self.wfile.flush()
        elif path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Length", "10")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"short")
            self.wfile.flush()
            self.close_connection = True
        else:
            self._send(404, b"missing")

    def do_POST(self):
        body = self._body()
        payload = json.dumps({
            "body": body.decode("latin1"),
            "content_type": self.headers.get("Content-Type"),
        }).encode()
        self._send(200, payload, [("Content-Type", "application/json")])


@contextlib.contextmanager
def running_server():
    Handler.seen_connections = set()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
