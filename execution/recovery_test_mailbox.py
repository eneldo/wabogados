#!/usr/bin/env python3
"""Isolated SMTP capture for recovery E2E. Never use as a production mail service.

Requires the backend dev extra (aiosmtpd). Only synthetic @example.com recipients
are accepted. Bind HTTP/SMTP ports to loopback on the Docker host, no real SMTP.
The in-memory HTTP inbox contains test links; logs intentionally omit bodies.
"""

import argparse
import json
import logging
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from aiosmtpd.controller import Controller

MAIL: list[dict[str, Any]] = []
LOCK = threading.Lock()


class SMTPHandler:
    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
        if not all(address.endswith("@example.com") for address in envelope.rcpt_tos):
            return "550 Only synthetic example.com recipients are allowed"
        message = BytesParser(policy=policy.default).parsebytes(envelope.original_content)
        plain = message.get_body(preferencelist=("plain",))
        with LOCK:
            MAIL.append({"to": envelope.rcpt_tos, "text": plain.get_content() if plain else ""})
        return "250 Captured in isolated test memory"


class InboxHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path not in {"/messages", "/health"}:
            self.send_error(404)
            return
        with LOCK:
            payload = json.dumps(MAIL if self.path == "/messages" else {"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--http-port", type=int, default=8025)
    args = parser.parse_args()
    logging.getLogger("mail.log").setLevel(logging.CRITICAL)
    controller = Controller(SMTPHandler(), hostname=args.bind, port=args.smtp_port)
    controller.start()
    try:
        ThreadingHTTPServer((args.bind, args.http_port), InboxHandler).serve_forever()
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
