"""Game entry point."""

import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of how script is invoked
_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from src.game.game import Game


def main() -> None:
    """Instantiate and run the game."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
