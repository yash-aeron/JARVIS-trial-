"""
security/permission_manager.py — Centralized Production Permission & Capability Sandboxing Controller.

Capabilities:
  1. Fine-grained capability checks (LOW, MEDIUM, HIGH, CRITICAL).
  2. High-risk action approval mode (interactive user prompt gate for CRITICAL/HIGH risk actions).
  3. Sandboxed capability scope restriction for third-party tools & plugins.
"""
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field
from observability.logger import logger


class SecurityPolicyModel(BaseModel):
    """Centralized security policy configuration."""
    require_approval_for_high_risk: bool = True
    allowed_capabilities: Set[str] = Field(default_factory=set)
    blocked_capabilities: Set[str] = Field(default_factory=set)
    capability_risk_levels: Dict[str, str] = Field(default_factory=lambda: {
        "system_control": "HIGH",
        "close_application": "MEDIUM",
        "open_application": "LOW",
        "read_context": "LOW",
        "recall_memory": "LOW",
        "delete_system_files": "CRITICAL",
        "modify_registry": "CRITICAL",
        "network_listen": "HIGH"
    })


class PermissionManager:
    """Centralized Security Controller for capability sandboxing and high-risk action approval."""

    def __init__(self, policy: Optional[SecurityPolicyModel] = None):
        self.policy = policy or SecurityPolicyModel()
        self._approved_correlations: Set[str] = set()

    def get_capability_risk(self, capability: str) -> str:
        """Return declared risk level for a capability ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')."""
        return self.policy.capability_risk_levels.get(capability, "LOW")

    def is_capability_allowed(self, capability: str, active_capabilities: Optional[List[str]] = None) -> bool:
        """Verify capability against global policy and active capability sandbox."""
        if capability in self.policy.blocked_capabilities:
            logger.warning(f"[PermissionManager] Capability '{capability}' is explicitly blocked by security policy.")
            return False

        if active_capabilities is not None and capability not in active_capabilities:
            logger.warning(f"[PermissionManager] Capability '{capability}' is outside active sandbox scope.")
            return False

        return True

    def requires_user_approval(self, capability: str) -> bool:
        """Check if capability risk level requires high-risk action approval."""
        risk = self.get_capability_risk(capability)
        if not self.policy.require_approval_for_high_risk:
            return False
        return risk in ["HIGH", "CRITICAL"]

    def grant_approval(self, correlation_id: str) -> None:
        """Record explicit user approval for a high-risk transaction."""
        self._approved_correlations.add(correlation_id)
        logger.info(f"[PermissionManager] High-risk approval granted for correlation ID '{correlation_id}'")

    def is_approved(self, correlation_id: str) -> bool:
        """Check if correlation ID has received user approval."""
        return correlation_id in self._approved_correlations

    def evaluate_request_security(self, capability: str, correlation_id: str) -> bool:
        """
        Master security gate check evaluating sandboxing & high-risk approval.
        Returns True if authorized; False if denied.
        """
        if not self.is_capability_allowed(capability):
            return False

        if self.requires_user_approval(capability) and not self.is_approved(correlation_id):
            logger.warning(f"[PermissionManager] Action '{capability}' requires explicit approval for CID '{correlation_id}'.")
            return False

        return True
