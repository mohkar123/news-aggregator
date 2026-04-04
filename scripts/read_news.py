#!/usr/bin/env python3
"""Thin shim — delegates to news_aggregator.cli.read_news.

Run directly::

    python scripts/read_news.py [options]

Or use the console-script entry point installed by Poetry::

    read-news [options]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from news_aggregator.cli.read_news import main

if __name__ == "__main__":
    main()
