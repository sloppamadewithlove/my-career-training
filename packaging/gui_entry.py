"""Frozen GUI entry point; worker is a separate console executable."""
from my_career_training.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
