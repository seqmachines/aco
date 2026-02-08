"""Module registry for discovering and instantiating QC modules."""

from __future__ import annotations

import logging
from typing import Type

from aco.engine.modules.base import QCModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Central registry for deterministic QC modules."""

    def __init__(self) -> None:
        self._modules: dict[str, Type[QCModule]] = {}

    def register(self, module_cls: Type[QCModule]) -> Type[QCModule]:
        """Register a QCModule subclass.

        Can be used as a decorator::

            @registry.register
            class MyModule(QCModule):
                name = "my_module"
                ...
        """
        name = module_cls.name
        if not name:
            raise ValueError(f"Module class {module_cls.__name__} has no name")
        if name in self._modules:
            logger.warning("Overwriting module '%s' in registry", name)
        self._modules[name] = module_cls
        return module_cls

    def get(self, name: str) -> Type[QCModule] | None:
        """Look up a module class by name."""
        return self._modules.get(name)

    def has(self, name: str) -> bool:
        """Check whether a module is registered."""
        return name in self._modules

    def all(self) -> dict[str, Type[QCModule]]:
        """Return all registered modules."""
        return dict(self._modules)

    def names(self) -> list[str]:
        """Return sorted list of registered module names."""
        return sorted(self._modules.keys())

    def info(self) -> list[dict[str, str]]:
        """Return metadata for every registered module."""
        out = []
        for name in sorted(self._modules):
            cls = self._modules[name]
            out.append({
                "name": name,
                "description": cls.description,
                "version": cls.version,
                "inputs": ", ".join(cls.input_patterns),
                "outputs": ", ".join(cls.output_names),
            })
        return out
