"""Compatibility facade over the domain service modules.

HTTP routers and new code import their concrete service module directly. This
facade keeps legacy helper imports patchable while downstream callers migrate.
"""

from __future__ import annotations

import sys
import types

from app.security import admin_auth
from app.services import (
    app_state_service,
    attachment_service,
    collection_service,
    document_service,
    health_service,
    memory_service,
    rag_service,
    research_service,
    runtime_context,
    shared_runtime,
    sources_service,
    system_service,
    usage_service,
    watcher_service,
)

_MODULES = (
    shared_runtime,
    rag_service,
    sources_service,
    research_service,
    watcher_service,
    memory_service,
    usage_service,
    health_service,
    app_state_service,
    attachment_service,
    document_service,
    collection_service,
    system_service,
    runtime_context,
)

_NAME_MODULES: dict[str, tuple[types.ModuleType, ...]] = {}
for _module in _MODULES:
    for _name in dir(_module):
        if not _name.startswith("__"):
            _NAME_MODULES[_name] = (*_NAME_MODULES.get(_name, ()), _module)
_NAME_MODULES["ADMIN_TOKEN"] = (admin_auth,)
_NAME_MODULES["ALLOW_LAN_SYSTEM"] = (admin_auth,)


class _ServiceFacade(types.ModuleType):
    def __getattr__(self, name: str):
        for module in _NAME_MODULES.get(name, ()):
            if hasattr(module, name):
                return getattr(module, name)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value) -> None:
        modules = _NAME_MODULES.get(name)
        if modules:
            for module in modules:
                setattr(module, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        modules = _NAME_MODULES.get(name)
        if modules:
            for module in modules:
                if hasattr(module, name):
                    delattr(module, name)
            return
        super().__delattr__(name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(_NAME_MODULES))


__all__ = sorted(_NAME_MODULES)
sys.modules[__name__].__class__ = _ServiceFacade
