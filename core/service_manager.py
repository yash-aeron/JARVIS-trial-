import asyncio
from typing import Dict, List, Any, Optional
from core.interfaces import IService
from observability.logger import logger

class ServiceManager:
    """Manages lifecycle (Start, Stop, Health Check, Auto-Restart) of all subsystem services."""
    
    def __init__(self):
        self._services: Dict[str, IService] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_running = False

    def register_service(self, service: IService) -> None:
        self._services[service.name] = service

    async def start_all(self) -> None:
        logger.info("Starting all registered services...")
        for name, service in self._services.items():
            try:
                await service.start()
                logger.info(f"Service '{name}' started successfully.")
            except Exception as e:
                logger.error(f"Failed to start service '{name}': {e}")
                
        self._is_running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop_all(self) -> None:
        self._is_running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            
        logger.info("Stopping all registered services...")
        for name, service in self._services.items():
            try:
                await service.stop()
                logger.info(f"Service '{name}' stopped.")
            except Exception as e:
                logger.error(f"Error stopping service '{name}': {e}")

    async def _health_check_loop(self) -> None:
        while self._is_running:
            await asyncio.sleep(30)  # Check health every 30 seconds
            for name, service in self._services.items():
                try:
                    healthy = await service.health_check()
                    if not healthy:
                        logger.warning(f"Service '{name}' failed health check! Attempting restart...")
                        await service.stop()
                        await service.start()
                        logger.info(f"Service '{name}' restarted successfully.")
                except Exception as e:
                    logger.error(f"Health check exception on service '{name}': {e}")
