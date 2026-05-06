"""Backwards-compat shim for `python cli.py <command>`.

The canonical entry point is `vamos <command>` (installed via pyproject.toml),
which routes to `vamos.cli:main`. This shim keeps the existing cron entries and
muscle memory working without any change.
"""
import sys

from vamos.cli import main

if __name__ == "__main__":
    sys.exit(main())
