import importlib
import pkgutil


def load_tools() -> None:
    """Import every tool module so its decorator registers the tool."""
    for module_info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
        if not module_info.name.rsplit(".", 1)[-1].startswith("_"):
            importlib.import_module(module_info.name)