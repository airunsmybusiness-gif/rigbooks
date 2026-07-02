#!/usr/bin/env python3
"""One-command launcher for OilForge.

    python run.py            # start on http://localhost:8899
    python run.py --port 9000
"""
import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OilForge locally")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    import uvicorn

    url = f"http://{args.host}:{args.port}"
    print(f"\n  🔥 OilForge running at {url}  (Ctrl+C to stop)\n")
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run("oilforge.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
