from __future__ import annotations

import importlib

from .core import EvalSuite


def load_suite(spec: str) -> EvalSuite:
    if ":" not in spec:
        raise ValueError("suite must be provided as module.path:object_name")
    module_name, object_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    suite = getattr(module, object_name)
    if not isinstance(suite, EvalSuite):
        raise TypeError(f"{spec} did not resolve to an EvalSuite")
    return suite
