"""Tiny local HTTP bridge consumed by Home Assistant (rest / rest_command).

Endpoints (JSON):
  GET  /health          liveness + module id
  GET  /status          normalized status (live values when the box is online)
  GET  /raw             raw ``GET /status/{moduleId}`` payload
  POST /set  {k: v}     write parameters (whitelist, see const.WRITABLE_PARAMS)
  POST /off             forced shutdown (WS_RESTART)
  POST /cmd  {code,data} send an arbitrary command code (for experiments)
"""

from __future__ import annotations

import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import const
from .client import CognitoAuth, FabaClient

log = logging.getLogger("faba_bridge")


def make_handler(client: FabaClient):
    started = time.time()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # noqa: D401 - quieter logging
            log.info("%s %s", self.command, self.path)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            data = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("JSON object expected")
            return data

        def do_GET(self):  # noqa: N802 - http.server API
            try:
                if self.path.startswith("/health"):
                    return self._send(200, {"ok": True, "module_id": client.module_id, "uptime": time.time() - started})
                if self.path.startswith("/status"):
                    return self._send(200, client.status())
                if self.path.startswith("/raw"):
                    return self._send(200, client.raw_status())
                return self._send(404, {"error": "not found"})
            except Exception as err:  # noqa: BLE001
                log.exception("GET %s failed", self.path)
                return self._send(502, {"error": str(err)})

        def do_POST(self):  # noqa: N802
            try:
                body = self._body()
                if self.path.startswith("/set"):
                    try:
                        return self._send(200, client.write_params(body))
                    except ValueError as err:
                        return self._send(400, {"error": str(err), "allowed": sorted(const.WRITABLE_PARAMS)})
                if self.path.startswith("/off"):
                    return self._send(200, client.power_off())
                if self.path.startswith("/cmd"):
                    return self._send(200, client.send_cmd(int(body["code"]), body.get("data") or {}))
                return self._send(404, {"error": "not found"})
            except ValueError as err:
                return self._send(400, {"error": str(err)})
            except Exception as err:  # noqa: BLE001
                log.exception("POST %s failed", self.path)
                return self._send(502, {"error": str(err)})

    return Handler


def serve(client: FabaClient, host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(client))
    log.info("faba-bridge listening on %s:%s", host, port)
    httpd.serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    user = os.environ.get("MYFABA_USER")
    password = os.environ.get("MYFABA_PASS")
    if not user or not password:
        raise SystemExit("MYFABA_USER and MYFABA_PASS must be set")
    auth = CognitoAuth(user, password)
    client = FabaClient(auth.id_token, module_id=os.environ.get("MYFABA_MODULE_ID") or None)
    serve(
        client,
        os.environ.get("FABA_BRIDGE_HOST", const.DEFAULT_LISTEN_HOST),
        int(os.environ.get("FABA_BRIDGE_PORT", const.DEFAULT_LISTEN_PORT)),
    )
