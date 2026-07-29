import asyncio
import time
from typing import Dict, List, Optional
from core.interfaces import IService
from core.models import ServiceState
from observability.logger import logger

class ServiceManager:
    """Production Service Manager with failure window tracking, restart threshold limits, and circuit breakers."""
    
    def __init__(
        self, 
        circuit_break_threshold: int = 3, 
        failure_window_sec: float = 60.0
    ):
        self.circuit_break_threshold = circuit_break_threshold
        self.failure_window_sec = failure_window_sec
        self._services: Dict[str, IService] = {}
        self._states: Dict[str, ServiceState] = {}
        self._failure_timestamps: Dict[str, List[float]] = {}

    def register_service(self, service: IService) -> None:
        self._services[service.name] = service
        self._states[service.name] = ServiceState.NEW
        self._failure_timestamps[service.name] = []
        logger.info(f"[ServiceManager] Registered service: '{service.name}'")

    async def start_service(self, name: str) -> bool:
        if name not in self._services:
            logger.error(f"[ServiceManager] Cannot start unknown service: '{name}'")
            return False
            
        svc = self._services[name]
        self._states[name] = ServiceState.STARTING
        
        # Check Failure Window & Circuit Breaker Threshold
        now = time.time()
        recent_failures = [t for t in self._failure_timestamps[name] if (now - t) <= self.failure_window_sec]
        self._failure_timestamps[name] = recent_failures
        
        if len(recent_failures) >= self.circuit_break_threshold:
            self._states[name] = ServiceState.DEGRADED
            logger.warning(f"[ServiceManager] Circuit breaker TRIPPED for service '{name}' ({len(recent_failures)} failures in last {self.failure_window_sec}s). Transitioned to DEGRADED.")
            return False
            
        try:
            await svc.start()
            self._states[name] = ServiceState.RUNNING
            logger.info(f"[ServiceManager] Service '{name}' is RUNNING.")
            return True
        except Exception as e:
            self._failure_timestamps[name].append(time.time())
            if len(self._failure_timestamps[name]) >= self.circuit_break_threshold:
                self._states[name] = ServiceState.DEGRADED
            else:
                self._states[name] = ServiceState.FAILED
            logger.error(f"[ServiceManager] Service '{name}' failed to start: {e}")
            return False

    async def stop_service(self, name: str) -> bool:
        if name not in self._services:
            return False
        svc = self._services[name]
        self._states[name] = ServiceState.STOPPING
        try:
            await svc.stop()
            self._states[name] = ServiceState.STOPPED
            logger.info(f"[ServiceManager] Service '{name}' is STOPPED.")
            return True
        except Exception as e:
            self._states[name] = ServiceState.FAILED
            logger.error(f"[ServiceManager] Service '{name}' failed to stop: {e}")
            return False

    async def start_all(self) -> None:
        for name in list(self._services.keys()):
            await self.start_service(name)

    async def stop_all(self) -> None:
        for name in list(self._services.keys()):
            await self.stop_service(name)

    def get_service_state(self, name: str) -> ServiceState:
        return self._states.get(name, ServiceState.FAILED)
