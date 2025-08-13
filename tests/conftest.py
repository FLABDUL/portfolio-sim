# tests/conftest.py
import sys, pathlib
# add project root (the parent of tests/) to sys.path so tests can import the module
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
