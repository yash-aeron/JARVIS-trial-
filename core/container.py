from typing import Dict, Any, Type, Optional, TypeVar

T = TypeVar('T')

class DependencyContainer:
    """Type-safe Dependency Injection Container supporting Interface & Type keys."""
    
    def __init__(self):
        self._singletons: Dict[Any, Any] = {}
        self._factories: Dict[Any, Any] = {}

    def register_singleton(self, key_type_or_name: Any, instance: Any) -> None:
        key = key_type_or_name if isinstance(key_type_or_name, (str, type)) else type(key_type_or_name)
        self._singletons[key] = instance
        # Also map string representation for fallback compatibility
        if isinstance(key, type):
            self._singletons[key.__name__] = instance

    def register_factory(self, key_type_or_name: Any, factory_fn: Any) -> None:
        key = key_type_or_name if isinstance(key_type_or_name, (str, type)) else type(key_type_or_name)
        self._factories[key] = factory_fn
        if isinstance(key, type):
            self._factories[key.__name__] = factory_fn

    def resolve(self, key_type_or_name: Type[T] | str) -> T:
        if key_type_or_name in self._singletons:
            return self._singletons[key_type_or_name]
        if isinstance(key_type_or_name, type) and key_type_or_name.__name__ in self._singletons:
            return self._singletons[key_type_or_name.__name__]
        if key_type_or_name in self._factories:
            return self._factories[key_type_or_name]()
        raise KeyError(f"Service for '{key_type_or_name}' is not registered in DependencyContainer.")
