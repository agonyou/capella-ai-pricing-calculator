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


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Clean logging
        sys.stderr.write(f"[Capella AI WebUI] {self.address_string()} - {format % args}\n")


def open_browser(url: str, delay: float = 1.0):
    time.sleep(delay)
    print(f"Opening {url} in your browser...")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Launch Capella AI Data Plane Pricing WebUI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to run the local server on (default 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    port = args.port
    url = f"http://localhost:{port}/pricing_calculator.html"

    # Find open port if 8080 is in use
    for p in range(port, port + 10):
        try:
            server = socketserver.TCPServer(("", p), Handler)
            port = p
            url = f"http://localhost:{port}/pricing_calculator.html"
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
