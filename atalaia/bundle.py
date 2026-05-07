from __future__ import annotations

import base64
import importlib
import importlib.util
import io
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from types import ModuleType
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


def _split_suite_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError("suite must be provided as module.path:object_name")
    module_name, object_name = spec.split(":", 1)
    if not module_name or not object_name:
        raise ValueError("suite must be provided as module.path:object_name")
    return module_name, object_name


def _top_level_package_name(module_name: str) -> str:
    return module_name.split(".", 1)[0]


def _find_bundle_source(module_name: str) -> tuple[Path, str]:
    package_name = _top_level_package_name(module_name)
    package_spec = importlib.util.find_spec(package_name)
    if package_spec is not None and package_spec.submodule_search_locations:
        return Path(package_spec.submodule_search_locations[0]), "package"

    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise ValueError(f"{module_name} is not importable")
    if spec.origin and spec.origin.endswith(".py"):
        return Path(spec.origin), "module"
    raise ValueError(f"{module_name} must resolve to a Python module or package")


def package_suite_bundle(suite_spec: str) -> dict[str, Any]:
    module_name, object_name = _split_suite_spec(suite_spec)
    source_path, source_kind = _find_bundle_source(module_name)
    archive = io.BytesIO()

    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zf:
        if source_kind == "module":
            zf.write(source_path, arcname=source_path.name)
        else:
            package_root = source_path
            for path in sorted(package_root.rglob("*")):
                if path.is_dir():
                    continue
                if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                    continue
                zf.write(path, arcname=str(path.relative_to(package_root.parent)))

    return {
        "format": "zip",
        "module_name": module_name,
        "object_name": object_name,
        "package_name": _top_level_package_name(module_name),
        "archive_base64": base64.b64encode(archive.getvalue()).decode("ascii"),
    }


@contextmanager
def _temporary_sys_path(path: str):
    sys.path.insert(0, path)
    try:
        yield
    finally:
        with suppress(ValueError):
            sys.path.remove(path)


@contextmanager
def _temporary_module_reload(module_name: str):
    saved_modules: dict[str, ModuleType] = {}
    prefixes = (module_name, _top_level_package_name(module_name))
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            saved_modules[name] = sys.modules.pop(name)
    try:
        yield
    finally:
        for name, module in saved_modules.items():
            sys.modules[name] = module


def _extract_zip_safely(zf: ZipFile, tmpdir: str) -> None:
    base_path = Path(tmpdir).resolve()
    for member in zf.infolist():
        target_path = (base_path / member.filename).resolve()
        if not target_path.is_relative_to(base_path):
            raise ValueError("bundle contains unsafe archive paths")
    zf.extractall(tmpdir)


def _load_suite_from_bundle(bundle: dict[str, Any], tmpdir: str):
    from .core import EvalSuite

    if bundle.get("format") != "zip":
        raise ValueError("unsupported suite bundle format")

    module_name = str(bundle.get("module_name", ""))
    object_name = str(bundle.get("object_name", ""))
    if not module_name or not object_name:
        raise ValueError("bundle is missing module_name or object_name")

    archive_base64 = bundle.get("archive_base64")
    if not isinstance(archive_base64, str) or not archive_base64:
        raise ValueError("bundle is missing archive_base64")

    archive_bytes = base64.b64decode(archive_base64.encode("ascii"))
    with ZipFile(io.BytesIO(archive_bytes)) as zf:
        _extract_zip_safely(zf, tmpdir)
    with _temporary_sys_path(tmpdir), _temporary_module_reload(module_name):
        module = importlib.import_module(module_name)
        suite = getattr(module, object_name)
        if not isinstance(suite, EvalSuite):
            raise TypeError(f"{module_name}:{object_name} did not resolve to an EvalSuite")
        return suite


@contextmanager
def open_suite_bundle(bundle: dict[str, Any]) -> Iterator[Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield _load_suite_from_bundle(bundle, tmpdir)


def load_suite_from_bundle(bundle: dict[str, Any]):
    with tempfile.TemporaryDirectory() as tmpdir:
        return _load_suite_from_bundle(bundle, tmpdir)
