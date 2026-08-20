#!/usr/bin/env python3
"""
Capella AI Data Plane - WebUI Launcher
Starts a local web server and automatically opens the interactive calculator in your default browser.

Usage:
  python3 run_webui.py
  python3 run_webui.py --port 8080
"""

import argparse
import http.server
import os
import socketserver
import sys
import threading
import time
import webbrowser

DEFAULT_PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="20" fill="#EA2328"/>
  <text x="50" y="70" font-size="65" font-family="Arial, Helvetica, sans-serif" font-weight="bold" fill="#ffffff" text-anchor="middle">C</text>
</svg>""".encode("utf-8")


class CapellaWebUIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # Route root '/' directly to pricing_calculator.html
        if self.path in ("/", ""):
            self.path = "/pricing_calculator.html"

        # Provide clean SVG favicon to prevent 404 logs
        if self.path == "/favicon.ico":
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(FAVICON_SVG)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(FAVICON_SVG)
            return

        return super().do_GET()

    def log_message(self, format, *args):
        # Filter out repetitive favicon or asset noise
        msg = format % args
        if "favicon.ico" not in msg:
            sys.stderr.write(f"[Capella AI WebUI] {self.address_string()} - {msg}\n")


def open_browser(url: str, delay: float = 0.8):
    time.sleep(delay)
    print(f"Opening {url} in your browser...")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Launch Capella AI Data Plane Pricing WebUI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to run the local server on (default 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    port = args.port
    url = f"http://localhost:{port}/"

    # Find open port if 8080 is in use
    for p in range(port, port + 10):
        try:
            server = socketserver.TCPServer(("", p), CapellaWebUIHandler)
            port = p
            url = f"http://localhost:{port}/"
            break
        except OSError:
            continue
    else:
        print(f"Error: Could not bind to any port between {args.port} and {args.port + 10}.")
        sys.exit(1)

    print("=" * 70)
    print("      CAPELLA AI DATA PLANE — INTERACTIVE PRICING & SIZING WEBUI")
    print("=" * 70)
    print(f"\n  >> WebUI URL:     {url}")
    print(f"  >> Serving from:  {DIRECTORY}")
    print("\n  Press Ctrl+C at any time to stop the server.\n" + "=" * 70)

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Capella AI WebUI] Shutting down web server. Goodbye!")
        server.server_close()


if __name__ == "__main__":
    main()
