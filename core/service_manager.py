import asyncio
import time
from typing import Dict, List, Optional
from core.interfaces import IService
from core.models import ServiceState
from observability.logger import logger

class CircuitBreaker:
    """Tracks consecutive service failures and manages cooldown threshold states."""
    
    def __init__(self, failure_threshold: int = 3, cooldown_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.consecutive_failures = 0
        self.last_failure_time = 0.0

    def record_failure(self) -> bool:
        """Records a failure. Returns True if circuit breaker trips into DEGRADED state."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        return self.consecutive_failures >= self.failure_threshold

    def record_success(self) -> None:
        self.consecutive_failures = 0

    @property
    def is_open(self) -> bool:
        if self.consecutive_failures >= self.failure_threshold:
            if time.time() - self.last_failure_time < self.cooldown_sec:
                return True
            # Cooldown passed, reset breaker to half-open
            self.consecutive_failures = 0
        return False

class ServiceManager:
    """Manages subsystem lifecycles with explicit ServiceState, Circuit Breakers, and Auto-Recovery policies."""
    
    def __init__(self):
        self._services: Dict[str, IService] = {}
        self._states: Dict[str, ServiceState] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def register_service(self, service: IService) -> None:
        name = service.name
        self._services[name] = service
        self._states[name] = ServiceState.NEW
        self._circuit_breakers[name] = CircuitBreaker()
        logger.info(f"[ServiceManager] Registered service '{name}' [Initial State: {ServiceState.NEW.value}]")

    def get_service_state(self, name: str) -> ServiceState:
        return self._states.get(name, ServiceState.STOPPED)

    async def start_service(self, name: str) -> bool:
        service = self._services.get(name)
        if not service:
            return False
            
        cb = self._circuit_breakers[name]
        if cb.is_open:
            logger.warning(f"[ServiceManager] Circuit breaker open for service '{name}'. Start aborted.")
            self._states[name] = ServiceState.DEGRADED
            return False
            
        try:
            self._states[name] = ServiceState.STARTING
            await service.start()
            self._states[name] = ServiceState.RUNNING
            cb.record_success()
            logger.info(f"[ServiceManager] Service '{name}' started successfully.")
            return True
        except Exception as e:
            logger.error(f"[ServiceManager] Error starting service '{name}': {e}")
            if cb.record_failure():
                self._states[name] = ServiceState.DEGRADED
            else:
                self._states[name] = ServiceState.FAILED
            return False

    async def stop_service(self, name: str) -> bool:
        service = self._services.get(name)
        if not service:
            return False
            
        try:
            self._states[name] = ServiceState.STOPPING
            await service.stop()
            self._states[name] = ServiceState.STOPPED
            logger.info(f"[ServiceManager] Service '{name}' stopped cleanly.")
            return True
        except Exception as e:
            logger.error(f"[ServiceManager] Error stopping service '{name}': {e}")
            self._states[name] = ServiceState.FAILED
            return False

    async def start_all(self) -> None:
        logger.info("[ServiceManager] Starting all registered services...")
        for name in self._services:
            await self.start_service(name)

    async def stop_all(self) -> None:
        logger.info("[ServiceManager] Stopping all registered services...")
        for name in list(self._services.keys()):
            await self.stop_service(name)
