"""Shared domain models used by UF and IF layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(slots=True)
class ExecutionRequest:
    scenario_id: str
    run_id: str
    agent_count: int = 4
    curriculum_level: int = 0
    seed: int = 1
    rare_case_injection: bool = False
    benchmark_mode: str = "baseline"
    target_time_acceleration: float = 60.0
    max_memory_utilization: float = 0.8
    preferred_device: str = "auto"
    motion_model_complexity: float = 1.0
    scenario_duration_s: float = 600.0
    control_hz: float = 20.0
    feature_plan: List[str] = field(default_factory=lambda: ["state_vector", "terrain", "threat"])
    curriculum_policy: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedExecutionRequest:
    scenario_id: str
    run_id: str
    agent_count: int
    curriculum_level: int
    seed: int
    rare_case_injection: bool
    benchmark_mode: str
    target_time_acceleration: float
    max_memory_utilization: float
    preferred_device: str
    motion_model_complexity: float
    scenario_duration_s: float
    control_dt: float
    feature_plan: List[str]
    curriculum_policy: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


@dataclass(slots=True)
class HardwareProfile:
    cpu_cores: int
    ram_bytes: int
    gpu_vram_bytes: int = 0
    gpu_enabled: bool = False
    accelerator_name: str = "cpu"


@dataclass(slots=True)
class HardwareInspectionContext:
    normalized_request: NormalizedExecutionRequest
    hardware_profile: HardwareProfile
    safe_ram_bytes: int
    safe_gpu_bytes: int
    warnings: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ScenarioInstance:
    scenario_id: str
    run_id: str
    seed: int
    curriculum_level: int
    agent_count: int
    rare_cases_enabled: bool
    difficulty: float
    ownship_spawn: List[List[float]]
    threat_spawn: List[List[float]]
    target_spawn: List[List[float]]
    terrain_heights: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScenarioPlanningContext:
    normalized_request: NormalizedExecutionRequest
    hardware_profile: HardwareProfile
    scenario_instance: ScenarioInstance
    warnings: List[str] = field(default_factory=list)


@dataclass(slots=True)
class RolloutPlan:
    parallel_rollouts: int
    estimated_env_step_per_sec: float
    estimated_time_acceleration: float
    device: str
    per_rollout_memory_bytes: int
    batch_memory_bytes: int
    benchmark_mode: str


@dataclass(slots=True)
class RolloutSizingContext:
    scenario_instance: ScenarioInstance
    hardware_profile: HardwareProfile
    rollout_plan: RolloutPlan
    warnings: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PartialExecutionBundle:
    scenario_instance: ScenarioInstance
    rollout_plan: RolloutPlan
    deterministic_seed: int
    benchmark_mode: str
    checksum: str


@dataclass(slots=True)
class ExecutionBundle:
    scenario_instance: ScenarioInstance
    rollout_plan: RolloutPlan
    deterministic_seed: int
    benchmark_mode: str
    agent_count: int
    reproducibility_manifest: Dict[str, Any]
    checksum: str


@dataclass(slots=True)
class OwnshipState:
    position_m: List[float]
    velocity_mps: List[float]
    quaternion_wxyz: List[float]
    angular_rate_rps: List[float]
    mass_kg: float
    aero_params: Dict[str, float]


@dataclass(slots=True)
class ThreatState:
    identifier: str
    position_m: List[float]
    velocity_mps: List[float]
    model_id: str = "constant_velocity"


@dataclass(slots=True)
class TargetState:
    identifier: str
    position_m: List[float]
    velocity_mps: List[float]


@dataclass(slots=True)
class EnvironmentState:
    sim_time_s: float
    terrain_reference: List[float]
    flags: Dict[str, Any]


@dataclass(slots=True)
class RadarState:
    track_ids: List[str] = field(default_factory=list)
    detected_ranges_m: List[float] = field(default_factory=list)
    mode: str = "search"


@dataclass(slots=True)
class SensorState:
    contact_count: int = 0
    quality: float = 1.0
    mode: str = "nominal"
    detection_confidence: float = 0.0


@dataclass(slots=True)
class AtmosphereState:
    density_kgpm3: float = 1.225
    wind_vector_mps: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    turbulence_level: float = 0.0


@dataclass(slots=True)
class DynamicsControl:
    throttle: float
    body_rate_cmd_rps: List[float]
    load_factor_cmd: float = 1.0


@dataclass(slots=True)
class DynamicsStepRequest:
    ownship: OwnshipState
    threats: List[ThreatState]
    targets: List[TargetState]
    environment: EnvironmentState
    control: DynamicsControl
    dt_internal: float
    agent_count: int
    radar: RadarState = field(default_factory=RadarState)
    sensor: SensorState = field(default_factory=SensorState)
    atmosphere: AtmosphereState = field(default_factory=AtmosphereState)
    rng_state: Dict[str, Any] = field(default_factory=dict)
    mode_flags: Dict[str, Any] = field(default_factory=dict)
    calibration_config: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EntityStateSet:
    ownship: OwnshipState
    threats: List[ThreatState]
    targets: List[TargetState]
    environment: EnvironmentState
    radar: RadarState
    sensor: SensorState
    atmosphere: AtmosphereState
    control: DynamicsControl
    dt_internal: float
    agent_count: int
    rng_state: Dict[str, Any]
    mode_flags: Dict[str, Any]
    calibration_config: Dict[str, Any]


@dataclass(slots=True)
class OwnshipPropagationContext:
    ownship_next: OwnshipState
    threats: List[ThreatState]
    targets: List[TargetState]
    environment: EnvironmentState
    radar: RadarState
    sensor: SensorState
    atmosphere: AtmosphereState
    dt_internal: float
    rng_state: Dict[str, Any]
    mode_flags: Dict[str, Any]
    calibration_config: Dict[str, Any]


@dataclass(slots=True)
class ThreatPropagationContext:
    ownship_next: OwnshipState
    threats_next: List[ThreatState]
    targets: List[TargetState]
    environment: EnvironmentState
    radar: RadarState
    sensor: SensorState
    atmosphere: AtmosphereState
    dt_internal: float
    rng_state: Dict[str, Any]
    mode_flags: Dict[str, Any]
    calibration_config: Dict[str, Any]


@dataclass(slots=True)
class EnvironmentPropagationContext:
    ownship_next: OwnshipState
    threats_next: List[ThreatState]
    targets_next: List[TargetState]
    environment_next: EnvironmentState
    radar_next: RadarState
    sensor_next: SensorState
    atmosphere_next: AtmosphereState
    dt_internal: float
    rng_state: Dict[str, Any]
    mode_flags: Dict[str, Any]
    calibration_config: Dict[str, Any]


@dataclass(slots=True)
class AeroCalibrationContext:
    ownship_next: OwnshipState
    threats_next: List[ThreatState]
    targets_next: List[TargetState]
    environment_next: EnvironmentState
    radar_next: RadarState
    sensor_next: SensorState
    atmosphere_next: AtmosphereState
    rng_state: Dict[str, Any]
    mode_flags: Dict[str, Any]
    calibration_notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class DynamicsStepResult:
    ownship: OwnshipState
    threats: List[ThreatState]
    targets: List[TargetState]
    environment: EnvironmentState
    radar: RadarState = field(default_factory=RadarState)
    sensor: SensorState = field(default_factory=SensorState)
    atmosphere: AtmosphereState = field(default_factory=AtmosphereState)
    rng_state: Dict[str, Any] = field(default_factory=dict)
    mode_flags: Dict[str, Any] = field(default_factory=dict)
    event_flags: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnvironmentRuntime:
    ownship: OwnshipState
    threats: List[ThreatState]
    targets: List[TargetState]
    environment: EnvironmentState
    radar: RadarState = field(default_factory=RadarState)
    sensor: SensorState = field(default_factory=SensorState)
    atmosphere: AtmosphereState = field(default_factory=AtmosphereState)
    rng_state: Dict[str, Any] = field(default_factory=dict)
    mode_flags: Dict[str, Any] = field(default_factory=dict)
    dt_internal: float = 0.01
    calibration_config: Dict[str, Any] = field(default_factory=dict)
    history: List["EnvironmentCheckpoint"] = field(default_factory=list)


@dataclass(slots=True)
class EnvironmentCheckpoint:
    runtime: EnvironmentRuntime
    step_index: int
    checksum: str
    metadata: Dict[str, Any]


@dataclass(slots=True)
class BranchRolloutRequest:
    runtime: EnvironmentRuntime
    runtime_source_spec: Dict[str, Any]
    branch_mode: str
    branch_controls: List[Dict[str, Any]]
    horizon: int
    reference_trajectories: Optional[List[List[Dict[str, Any]]]] = None
    tolerance: float = 1e-9
    clone_policy: str = "checkpoint_restore"


@dataclass(slots=True)
class ValidatedCheckpoint:
    checkpoint: EnvironmentCheckpoint
    required_fields: List[str]


@dataclass(slots=True)
class BranchSourceRuntime:
    runtime: EnvironmentRuntime
    checkpoint_metadata: Dict[str, Any]


@dataclass(slots=True)
class BranchControlBatch:
    mode: str
    control_sequences: List[List[Dict[str, Any]]]


@dataclass(slots=True)
class BranchRuntimeBatch:
    source_checkpoint: EnvironmentCheckpoint
    runtimes: List[EnvironmentRuntime]


@dataclass(slots=True)
class PreparedBranchBatch:
    source_checkpoint: EnvironmentCheckpoint
    runtimes: List[EnvironmentRuntime]
    control_sequences: List[List[Dict[str, Any]]]
    horizon: int
    reference_trajectories: Optional[List[List[Dict[str, Any]]]]
    tolerance: float


@dataclass(slots=True)
class BranchTrajectory:
    states: List[Dict[str, Any]]
    event_log: List[Dict[str, Any]]


@dataclass(slots=True)
class EnvironmentBranchTrajectoryBatch:
    trajectories: List[BranchTrajectory]
    source_checkpoint: EnvironmentCheckpoint


@dataclass(slots=True)
class BranchValidationReport:
    deterministic: bool
    source_immutable: bool
    branch_isolated: bool
    max_abs_error: float
    mismatch_count: int


@dataclass(slots=True)
class BranchRuntimeResult:
    checkpoint: EnvironmentCheckpoint
    branch_count: int
    branch_trajectories: List[BranchTrajectory]
    validation_report: BranchValidationReport
    metadata: Dict[str, Any]


@dataclass(slots=True)
class ObservationRequest:
    ownships: List[OwnshipState]
    threats: List[ThreatState]
    environment: EnvironmentState
    extension_channels: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VehicleFeatureContext:
    ownships: List[OwnshipState]
    threats: List[ThreatState]
    environment: EnvironmentState
    vehicle_features: List[List[float]]
    masks: List[List[int]]


@dataclass(slots=True)
class TerrainFeatureContext:
    ownships: List[OwnshipState]
    threats: List[ThreatState]
    environment: EnvironmentState
    vehicle_features: List[List[float]]
    terrain_features: List[List[float]]
    masks: List[List[int]]


@dataclass(slots=True)
class ThreatFeatureContext:
    ownships: List[OwnshipState]
    environment: EnvironmentState
    vehicle_features: List[List[float]]
    terrain_features: List[List[float]]
    threat_features: List[List[float]]
    masks: List[List[int]]


@dataclass(slots=True)
class ObservationFeatureSet:
    features: List[List[float]]
    masks: List[List[int]]
    clip_events: int = 0


@dataclass(slots=True)
class ObservationAssemblyContext:
    normalized_features: ObservationFeatureSet
    observation_masks: List[List[int]]
    extension_channels: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ObservationBatch:
    features: List[List[float]]
    masks: List[List[int]]
    schema_version: str
    extension_channels: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationRequest:
    run_id: str
    revision: str
    hardware_profile: HardwareProfile
    config: Dict[str, Any]
    seed_bundle: Dict[str, int]
    metrics: Dict[str, float]
    benchmark_counters: Dict[str, float]
    feature_plan: Sequence[str] = field(default_factory=tuple)


@dataclass(slots=True)
class EvaluationMetadataContext:
    evaluation_request: EvaluationRequest
    metadata: Dict[str, Any]


@dataclass(slots=True)
class BenchmarkMetricsContext:
    metadata: Dict[str, Any]
    benchmark_metrics: Dict[str, float]
    learning_metrics: Dict[str, float]


@dataclass(slots=True)
class RankingContext:
    metadata: Dict[str, Any]
    benchmark_metrics: Dict[str, float]
    ranked_groups: Dict[str, Dict[str, float]]


@dataclass(slots=True)
class ScopeAuditContext:
    metadata: Dict[str, Any]
    benchmark_metrics: Dict[str, float]
    ranked_groups: Dict[str, Dict[str, float]]
    scope_findings: List[str]


@dataclass(slots=True)
class ReportAssemblyContext:
    metadata: Dict[str, Any]
    benchmark_metrics: Dict[str, float]
    ranked_groups: Dict[str, Dict[str, float]]
    scope_findings: List[str]
    manifest: Dict[str, Any]


@dataclass(slots=True)
class EvaluationReportBundle:
    run_id: str
    benchmark_metrics: Dict[str, float]
    ranked_groups: Dict[str, Dict[str, float]]
    scope_findings: List[str]
    manifest: Dict[str, Any]
