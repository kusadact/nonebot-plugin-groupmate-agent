import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SRC = Path(__file__).resolve().parents[1] / "src" / "nonebot_plugin_groupmate_agent"


def install_package_stub(package_name: str) -> ModuleType:
    package = ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    return package


def load_module(module_name: str, relative_path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, SRC / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
