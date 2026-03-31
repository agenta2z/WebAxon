"""Entry point for running the WebAxon sidecar as a module.

Usage:
    python -m sidecar                          # Uses environment variables
    python -m sidecar --port 18800 --headless  # Uses CLI args (overrides env)
"""

import sys

if __name__ == "__main__":
    # If CLI args provided (beyond script name), use argparse-based main()
    if len(sys.argv) > 1:
        from .server import main
        main()
    else:
        # No CLI args: read config from environment variables
        from .server import run_server
        run_server()
