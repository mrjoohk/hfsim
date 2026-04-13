"""IF-03 integration module."""

from __future__ import annotations

from hf_sim.models import BranchRolloutRequest, BranchRuntimeResult
from uf.if03_snapshot import (
    capture_environment_checkpoint,
    clone_environment_runtime_batch,
    inject_branch_controls,
    materialize_branch_source_runtime,
    normalize_branch_control_batch,
    package_branch_runtime_result,
    rollout_branch_batch_with_environment_kernel,
    validate_checkpoint_completeness,
    verify_branch_isolation_and_determinism,
)


def if_03_branch_snapshot_rollout(branch_rollout_request: BranchRolloutRequest) -> BranchRuntimeResult:
    """Capture, branch, and roll out full-environment runtime checkpoints."""
    checkpoint = capture_environment_checkpoint(branch_rollout_request)
    validated = validate_checkpoint_completeness(checkpoint)
    _ = materialize_branch_source_runtime(validated)
    control_batch = normalize_branch_control_batch(branch_rollout_request)
    runtime_batch = clone_environment_runtime_batch(validated, control_batch)
    prepared = inject_branch_controls(runtime_batch, control_batch, branch_rollout_request)
    trajectories = rollout_branch_batch_with_environment_kernel(prepared)
    validation = verify_branch_isolation_and_determinism(prepared, trajectories)
    return package_branch_runtime_result(trajectories, validation)
