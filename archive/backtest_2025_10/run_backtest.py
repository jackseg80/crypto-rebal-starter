"""
Wrapper script to run backtest

Adds project root to sys.path to allow imports
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run
from services.ml.bourse.test_backtest import main

if __name__ == "__main__":
    main()
