from typing import Dict, Any, Type, Optional, TypeVar

T = TypeVar('T')

class DependencyContainer:
    """Dependency Injection Container managing service lifecycles."""
    
    def __init__(self):
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Any] = {}

    def register_singleton(self, interface_or_name: Any, instance: Any) -> None:
        key = interface_or_name if isinstance(interface_or_name, str) else interface_or_name.__name__
        self._singletons[key] = instance

    def register_factory(self, interface_or_name: Any, factory_fn: Any) -> None:
        key = interface_or_name if isinstance(interface_or_name, str) else interface_or_name.__name__
        self._factories[key] = factory_fn

    def resolve(self, interface_or_name: Any) -> Any:
        key = interface_or_name if isinstance(interface_or_name, str) else interface_or_name.__name__
        if key in self._singletons:
            return self._singletons[key]
        if key in self._factories:
            return self._factories[key]()
        raise KeyError(f"Service '{key}' is not registered in DependencyContainer.")
