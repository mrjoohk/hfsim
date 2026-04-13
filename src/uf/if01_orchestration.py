"""UF implementations for IF-01 orchestration."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
from dataclasses import asdict

from hf_sim.models import (
    ExecutionBundle,
    ExecutionRequest,
    HardwareInspectionContext,
    HardwareProfile,
    NormalizedExecutionRequest,
    PartialExecutionBundle,
    RolloutPlan,
    RolloutSizingContext,
    ScenarioInstance,
    ScenarioPlanningContext,
)


def parse_execution_config(execution_request: ExecutionRequest) -> NormalizedExecutionRequest:
    """Parse execution request into normalized config."""
    if execution_request is None:
        raise ValueError("execution_request cannot be None")

    warnings: list[str] = []
    agent_count = min(4, max(1, execution_request.agent_count))
    if agent_count != execution_request.agent_count:
        warnings.append("agent_count_clipped")

    curriculum_level = min(10, max(0, execution_request.curriculum_level))
    if curriculum_level != execution_request.curriculum_level:
        warnings.append("curriculum_level_clipped")

    if not execution_request.scenario_id:
        raise ValueError("scenario_id is required")
    if not execution_request.run_id:
        raise ValueError("run_id is required")
    if execution_request.control_hz <= 0.0:
        raise ValueError("control_hz must be > 0")

    benchmark_mode = execution_request.benchmark_mode.lower().strip() or "baseline"
    if benchmark_mode not in {"baseline", "stress", "eval"}:
        warnings.append("benchmark_mode_reset")
        benchmark_mode = "baseline"

    return NormalizedExecutionRequest(
        scenario_id=execution_request.scenario_id,
        run_id=execution_request.run_id,
        agent_count=agent_count,
        curriculum_level=curriculum_level,
        seed=max(0, execution_request.seed % (2**31 - 1)),
        rare_case_injection=bool(execution_request.rare_case_injection),
        benchmark_mode=benchmark_mode,
        target_time_acceleration=max(1.0, execution_request.target_time_acceleration),
        max_memory_utilization=min(0.95, max(0.1, execution_request.max_memory_utilization)),
        preferred_device=execution_request.preferred_device.lower().strip() or "auto",
        motion_model_complexity=max(0.1, execution_request.motion_model_complexity),
        scenario_duration_s=max(1.0, execution_request.scenario_duration_s),
        control_dt=1.0 / execution_request.control_hz,
        feature_plan=list(execution_request.feature_plan),
        curriculum_policy=dict(execution_request.curriculum_policy),
        warnings=warnings,
    )


def inspect_hardware_profile(normalized_request: NormalizedExecutionRequest) -> HardwareInspectionContext:
    """Inspect hardware profile and derive safe budgets."""
    cpu_cores = max(1, os.cpu_count() or 1)
    ram_bytes = normalized_request.curriculum_policy.get("ram_bytes", 16 * 1024**3)
    gpu_vram_bytes = normalized_request.curriculum_policy.get("gpu_vram_bytes", 8 * 1024**3)
    gpu_enabled = normalized_request.preferred_device != "cpu" and gpu_vram_bytes > 0
    accelerator_name = "gpu" if gpu_enabled else "cpu"

    if ram_bytes <= 0:
        raise RuntimeError("invalid hardware profile")
    if gpu_enabled and gpu_vram_bytes <= 0:
        gpu_enabled = False
        accelerator_name = "cpu"

    safe_ram_bytes = int(ram_bytes * normalized_request.max_memory_utilization)
    safe_gpu_bytes = int(gpu_vram_bytes * normalized_request.max_memory_utilization) if gpu_enabled else 0
    warnings: list[str] = []
    if not gpu_enabled:
        warnings.append("gpu_disabled_or_unavailable")

    return HardwareInspectionContext(
        normalized_request=normalized_request,
        hardware_profile=HardwareProfile(
            cpu_cores=cpu_cores,
            ram_bytes=ram_bytes,
            gpu_vram_bytes=gpu_vram_bytes if gpu_enabled else 0,
            gpu_enabled=gpu_enabled,
            accelerator_name=accelerator_name,
        ),
        safe_ram_bytes=safe_ram_bytes,
        safe_gpu_bytes=safe_gpu_bytes,
        warnings=warnings,
    )


def synthesize_scenario(hardware_inspection_context: HardwareInspectionContext) -> ScenarioPlanningContext:
    """Synthesize a deterministic learnability-first scenario."""
    normalized_request = hardware_inspection_context.normalized_request
    seed = normalized_request.seed
    rng = random.Random(seed)
    warnings = list(hardware_inspection_context.warnings)

    rare_cases_enabled = normalized_request.rare_case_injection and normalized_request.benchmark_mode != "baseline"
    if normalized_request.rare_case_injection and not rare_cases_enabled:
        warnings.append("rare_cases_disabled_for_baseline")

    difficulty = 0.2 + 0.1 * normalized_request.curriculum_level
    ownship_spawn = [[rng.uniform(-500.0, 500.0), rng.uniform(-500.0, 500.0), 1000.0 + 50.0 * idx] for idx in range(normalized_request.agent_count)]
    threat_spawn = [[2500.0 + 100.0 * idx, 1000.0 * ((idx % 2) * 2 - 1), 900.0] for idx in range(max(1, normalized_request.agent_count // 2))]
    target_spawn = [[5000.0, 500.0 * idx, 0.0] for idx in range(2)]
    terrain_heights = [100.0 + 10.0 * math.sin(idx) for idx in range(16)]

    scenario = ScenarioInstance(
        scenario_id=normalized_request.scenario_id,
        run_id=normalized_request.run_id,
        seed=seed,
        curriculum_level=normalized_request.curriculum_level,
        agent_count=normalized_request.agent_count,
        rare_cases_enabled=rare_cases_enabled,
        difficulty=difficulty,
        ownship_spawn=ownship_spawn,
        threat_spawn=threat_spawn,
        target_spawn=target_spawn,
        terrain_heights=terrain_heights,
        metadata={
            "feature_plan": normalized_request.feature_plan,
            "benchmark_mode": normalized_request.benchmark_mode,
            "target_time_acceleration": normalized_request.target_time_acceleration,
        },
    )
    return ScenarioPlanningContext(
        normalized_request=normalized_request,
        hardware_profile=hardware_inspection_context.hardware_profile,
        scenario_instance=scenario,
        warnings=warnings,
    )


def size_rollout_batch(scenario_planning_context: ScenarioPlanningContext) -> RolloutSizingContext:
    """Size rollout batch for available hardware."""
    request = scenario_planning_context.normalized_request
    hardware = scenario_planning_context.hardware_profile
    complexity = request.motion_model_complexity
    per_rollout_memory_bytes = int((48 * 1024**2) * complexity * request.agent_count)
    if per_rollout_memory_bytes <= 0 or math.isnan(float(per_rollout_memory_bytes)):
        raise ValueError("invalid sizing estimate")

    safe_memory = int(hardware.ram_bytes * request.max_memory_utilization)
    if per_rollout_memory_bytes > safe_memory:
        raise MemoryError("single rollout exceeds memory budget")

    parallel_rollouts = max(1, safe_memory // per_rollout_memory_bytes)
    device = "gpu" if hardware.gpu_enabled else "cpu"
    estimated_env_step_per_sec = (hardware.cpu_cores * 500.0 * parallel_rollouts) / complexity
    estimated_time_acceleration = estimated_env_step_per_sec * request.control_dt
    if device == "gpu":
        estimated_env_step_per_sec *= 1.5
        estimated_time_acceleration *= 1.5

    rollout_plan = RolloutPlan(
        parallel_rollouts=parallel_rollouts,
        estimated_env_step_per_sec=estimated_env_step_per_sec,
        estimated_time_acceleration=max(estimated_time_acceleration, request.target_time_acceleration),
        device=device,
        per_rollout_memory_bytes=per_rollout_memory_bytes,
        batch_memory_bytes=per_rollout_memory_bytes * parallel_rollouts,
        benchmark_mode=request.benchmark_mode,
    )
    return RolloutSizingContext(
        scenario_instance=scenario_planning_context.scenario_instance,
        hardware_profile=hardware,
        rollout_plan=rollout_plan,
        warnings=list(scenario_planning_context.warnings),
    )


def assemble_execution_bundle(rollout_sizing_context: RolloutSizingContext) -> PartialExecutionBundle:
    """Assemble a partial execution bundle."""
    scenario = rollout_sizing_context.scenario_instance
    if not scenario.scenario_id:
        raise ValueError("scenario_id required")
    if scenario.agent_count != len(scenario.ownship_spawn):
        raise ValueError("agent_count mismatch")

    payload = json.dumps(
        {
            "scenario_id": scenario.scenario_id,
            "run_id": scenario.run_id,
            "seed": scenario.seed,
            "agent_count": scenario.agent_count,
            "parallel_rollouts": rollout_sizing_context.rollout_plan.parallel_rollouts,
        },
        sort_keys=True,
    ).encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()

    return PartialExecutionBundle(
        scenario_instance=scenario,
        rollout_plan=rollout_sizing_context.rollout_plan,
        deterministic_seed=scenario.seed,
        benchmark_mode=rollout_sizing_context.rollout_plan.benchmark_mode,
        checksum=checksum,
    )


def finalize_execution_bundle(partial_bundle: PartialExecutionBundle) -> ExecutionBundle:
    """Finalize the simulator-ready execution bundle."""
    rollout_plan = partial_bundle.rollout_plan
    if rollout_plan is None:
        raise RuntimeError("rollout_plan missing")
    expected_checksum = hashlib.sha256(
        json.dumps(
            {
                "scenario_id": partial_bundle.scenario_instance.scenario_id,
                "run_id": partial_bundle.scenario_instance.run_id,
                "seed": partial_bundle.deterministic_seed,
                "agent_count": partial_bundle.scenario_instance.agent_count,
                "parallel_rollouts": rollout_plan.parallel_rollouts,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if expected_checksum != partial_bundle.checksum:
        raise ValueError("bundle integrity failure")

    return ExecutionBundle(
        scenario_instance=partial_bundle.scenario_instance,
        rollout_plan=rollout_plan,
        deterministic_seed=partial_bundle.deterministic_seed,
        benchmark_mode=partial_bundle.benchmark_mode,
        agent_count=partial_bundle.scenario_instance.agent_count,
        reproducibility_manifest={
            "scenario_id": partial_bundle.scenario_instance.scenario_id,
            "run_id": partial_bundle.scenario_instance.run_id,
            "seed": partial_bundle.deterministic_seed,
            "rollout_plan": asdict(rollout_plan),
        },
        checksum=partial_bundle.checksum,
    )
