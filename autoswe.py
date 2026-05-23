#!/usr/bin/env python3
"""autoswe.py — autoSWE GitHub Issue Agent (Claude Code integration)

Entry point only — delegates to autoswe/ package.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from autoswe.cli import main

if __name__ == "__main__":
    main()
