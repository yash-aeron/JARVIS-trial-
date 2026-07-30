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
    # Tools dispatch on args["action"], so a destructive action can arrive under a
    # low-risk capability. These override the capability's declared risk.
    action_risk_levels: Dict[str, str] = Field(default_factory=lambda: {
        "kill": "HIGH",
        "close": "MEDIUM",
        "terminate": "MEDIUM",
        "shutdown": "CRITICAL",
        "restart": "CRITICAL",
        "reboot": "CRITICAL",
        "sleep": "HIGH",
        "hibernate": "HIGH",
        "lock": "MEDIUM",
        "logoff": "HIGH",
    })
    # Read-only actions carry no side effects, so they may lower an otherwise
    # high-risk capability (e.g. reading CPU/RAM under "system_control").
    read_only_actions: Dict[str, str] = Field(default_factory=lambda: {
        "get_status": "LOW",
        "status": "LOW",
        "get_metrics": "LOW",
        "hardware_info": "LOW",
        "list": "LOW",
        "snapshot": "LOW",
        "clipboard": "LOW",
        "recall": "LOW",
        "search": "LOW",
    })


_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class PermissionManager:
    """Centralized Security Controller for capability sandboxing and high-risk action approval."""

    def __init__(self, policy: Optional[SecurityPolicyModel] = None):
        self.policy = policy or SecurityPolicyModel()
        self._approved_correlations: Set[str] = set()

    def get_capability_risk(self, capability: str, args: Optional[Dict] = None) -> str:
        """
        Return the effective risk level for a capability ('LOW'..'CRITICAL').

        When the request carries an `action`, the higher of the capability risk and
        the action risk wins — a destructive action must not inherit a low-risk
        capability's rating.
        """
        risk = self.policy.capability_risk_levels.get(capability, "LOW")
        if args:
            action = args.get("action")
            if isinstance(action, str):
                key = action.strip().lower()
                action_risk = self.policy.action_risk_levels.get(key)
                if action_risk and _RISK_ORDER[action_risk] > _RISK_ORDER[risk]:
                    return action_risk
                read_only_risk = self.policy.read_only_actions.get(key)
                if read_only_risk and _RISK_ORDER[read_only_risk] < _RISK_ORDER[risk]:
                    return read_only_risk
        return risk

    def is_capability_allowed(self, capability: str, active_capabilities: Optional[List[str]] = None) -> bool:
        """Verify capability against global policy and active capability sandbox."""
        if capability in self.policy.blocked_capabilities:
            logger.warning(f"[PermissionManager] Capability '{capability}' is explicitly blocked by security policy.")
            return False

        # An empty allowlist means "no allowlist configured"; a populated one is
        # authoritative and must deny anything absent from it.
        if self.policy.allowed_capabilities and capability not in self.policy.allowed_capabilities:
            logger.warning(f"[PermissionManager] Capability '{capability}' is not in the policy allowlist.")
            return False

        if active_capabilities is not None and capability not in active_capabilities:
            logger.warning(f"[PermissionManager] Capability '{capability}' is outside active sandbox scope.")
            return False

        return True

    def requires_user_approval(self, capability: str, args: Optional[Dict] = None) -> bool:
        """Check if capability risk level requires high-risk action approval."""
        risk = self.get_capability_risk(capability, args)
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

    def evaluate_request_security(
        self,
        capability: str,
        correlation_id: str,
        args: Optional[Dict] = None,
        active_capabilities: Optional[List[str]] = None,
    ) -> bool:
        """
        Master security gate check evaluating sandboxing & high-risk approval.
        Returns True if authorized; False if denied.
        """
        if not self.is_capability_allowed(capability, active_capabilities):
            return False

        if self.requires_user_approval(capability, args) and not self.is_approved(correlation_id):
            risk = self.get_capability_risk(capability, args)
            logger.warning(
                f"[PermissionManager] Action '{capability}' (risk {risk}) requires explicit "
                f"approval for CID '{correlation_id}'."
            )
            return False

        return True
