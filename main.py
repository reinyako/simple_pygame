"""Titik masuk GEMA: python main.py"""

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from gema.app import main  # noqa: E402

if __name__ == "__main__":
    main()
