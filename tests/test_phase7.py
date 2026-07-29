"""
tests/test_phase7.py — Integration and unit test suite for Phase 7 Security & Permissions.
"""
import pytest
import os
import uuid

from core.app import bootstrap_container
from security.permission_manager import PermissionManager, SecurityPolicyModel
from automation.executor import PlanExecutor
from core.models import ExecutionPlanModel, PlanStepModel


def test_permission_manager_risk_level_assessment():
    """Verify capability risk level classification and default policy rules."""
    pm = PermissionManager()

    assert pm.get_capability_risk("read_context") == "LOW"
    assert pm.get_capability_risk("system_control") == "HIGH"
    assert pm.get_capability_risk("delete_system_files") == "CRITICAL"


def test_high_risk_action_approval_gate():
    """Verify high-risk action approval requirement and grant flow."""
    pm = PermissionManager()
    cid = f"cid_sec_{uuid.uuid4()}"

    # Action requires approval
    assert pm.requires_user_approval("system_control") is True
    assert pm.evaluate_request_security("system_control", cid) is False

    # Grant approval
    pm.grant_approval(cid)
    assert pm.is_approved(cid) is True
    assert pm.evaluate_request_security("system_control", cid) is True


def test_capability_sandboxing_blocked_policy():
    """Verify capability sandboxing when a capability is explicitly blocked."""
    policy = SecurityPolicyModel(blocked_capabilities={"delete_system_files"})
    pm = PermissionManager(policy=policy)
    cid = "cid_blocked_1"

    assert pm.is_capability_allowed("delete_system_files") is False
    assert pm.evaluate_request_security("delete_system_files", cid) is False


@pytest.mark.asyncio
async def test_plan_executor_security_gate_integration():
    """Verify PlanExecutor blocks execution when PermissionManager denies permission."""
    container = bootstrap_container()
    executor: PlanExecutor = container.resolve(PlanExecutor)
    pm: PermissionManager = container.resolve(PermissionManager)

    # Explicitly block capability
    pm.policy.blocked_capabilities.add("open_application")

    plan = ExecutionPlanModel(
        plan_id="plan_sec_1",
        correlation_id=str(uuid.uuid4()),
        user_goal="Open Notepad",
        steps=[
            PlanStepModel(
                step_id=1, 
                capability="open_application", 
                args={"app_name": "notepad"},
                expected_observation="Notepad window opened"
            )
        ]
    )

    results = await executor.execute_plan(plan)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "Permission denied" in results[0].error
