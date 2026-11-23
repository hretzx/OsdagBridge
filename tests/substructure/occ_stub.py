"""Stand-in for pythonocc when it is not installed (CI and this sandbox).

The IFC export path never calls OpenCASCADE, but some modules it imports do
`from OCC.Core... import ...` at import time. When the real library is
present this module does nothing.
"""
import importlib.abc
import importlib.machinery
import sys
from unittest.mock import MagicMock


class _OccFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name == "OCC" or name.startswith("OCC."):
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        mod = MagicMock(name=spec.name)
        mod.__path__ = []
        mod.__spec__ = spec
        return mod

    def exec_module(self, module):
        pass


def install():
    try:
        import OCC.Core  # noqa: F401  (real pythonocc available)
        return False
    except ImportError:
        sys.meta_path.insert(0, _OccFinder())
        return True
