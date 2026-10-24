"""Private helper: explicit worker mode preserves the parent's JSON pipes."""
import sys

from my_career_training.__main__ import main

if __name__ == "__main__":
    if not {"--worker", "--self-test"}.intersection(sys.argv[1:]):
        message = "This is an internal helper. Open My Career Training from its shortcut instead."
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "My Career Training", 0x40)
        elif sys.stderr is not None:
            sys.stderr.write(message + "\n")
        raise SystemExit(2)
    raise SystemExit(main())
