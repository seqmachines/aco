"""Deterministic QC module framework.

Provides a plugin system for registering and running deterministic QC
modules as an alternative to LLM-generated scripts.  Each module is a
subclass of `QCModule` that declares its inputs, outputs, and implements
a `run()` method.

Usage:
    from aco.engine.modules import registry

    # Discover all registered modules
    for name, module_cls in registry.all().items():
        print(name, module_cls.description)

    # Run a specific module
    module = registry.get("barcode_validator")()
    module.validate_inputs(inputs)
    result = module.run(inputs, output_dir)
"""

from aco.engine.modules.base import QCModule, ModuleResult
from aco.engine.modules.registry import ModuleRegistry

# Singleton registry
registry = ModuleRegistry()

# Auto-register built-in modules
from aco.engine.modules import barcode_validator  # noqa: E402, F401
from aco.engine.modules import sequencing_health  # noqa: E402, F401
from aco.engine.modules import read_structure_checker  # noqa: E402, F401

__all__ = ["QCModule", "ModuleResult", "ModuleRegistry", "registry"]
