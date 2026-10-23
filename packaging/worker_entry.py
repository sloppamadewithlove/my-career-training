"""Console entry preserves JSON-line pipes when the GUI is windowless."""
import sys

from my_career_training.__main__ import main

if __name__ == "__main__":
    if "--worker" not in sys.argv:
        sys.argv.insert(1, "--worker")
    raise SystemExit(main())
