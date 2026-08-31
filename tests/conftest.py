"""Test bootstrap: make ``import user.reservoir`` work from any working
directory. WeeWX stubbing is done inside ``test_reservoir.py`` itself (it must
run before the module under test is imported)."""

import os
import sys

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "bin"))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)
