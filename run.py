"""Launch Function Forge."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from function_forge.app import main

if __name__ == "__main__":
    main()
