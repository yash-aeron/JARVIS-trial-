from typing import Dict, Any, Type, Optional, TypeVar, Callable

T = TypeVar('T')

class DependencyContainer:
    """Strict Type-Safe Dependency Injection Container requiring Class & Interface keys."""
    
    def __init__(self):
        self._singletons: Dict[Type[Any], Any] = {}
        self._factories: Dict[Type[Any], Callable[['DependencyContainer'], Any]] = {}

    def register_singleton(self, key_type: Type[T], instance: T) -> None:
        if not isinstance(key_type, type):
            raise TypeError(f"Container key must be a Class or Interface Type, got '{type(key_type)}'")
        self._singletons[key_type] = instance

    def register_factory(self, key_type: Type[T], factory_fn: Callable[['DependencyContainer'], T]) -> None:
        if not isinstance(key_type, type):
            raise TypeError(f"Container key must be a Class or Interface Type, got '{type(key_type)}'")
        self._factories[key_type] = factory_fn

    def resolve(self, key_type: Type[T]) -> T:
        if not isinstance(key_type, type):
            raise TypeError(f"Container resolve key must be a Class or Interface Type, got '{type(key_type)}'")
            
        if key_type in self._singletons:
            return self._singletons[key_type]
            
        if key_type in self._factories:
            instance = self._factories[key_type](self)
            self._singletons[key_type] = instance  # Cache factory output as singleton
            return instance
            
        raise KeyError(f"Type '{key_type.__name__}' is not registered in DependencyContainer.")
