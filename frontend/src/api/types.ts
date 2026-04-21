export interface Entry {
  branch_id: string;
  step_index: number;
  sim_time_s: number;
  ownship: {
    position_m: [number, number, number];
    velocity_mps: [number, number, number];
    quaternion_wxyz: [number, number, number, number];
    angular_rate_rps: [number, number, number];
    speed_mps: number;
    altitude_m: number;
    roll_deg: number;
    pitch_deg: number;
    heading_deg: number;
  };
  control: {
    throttle: number;
    body_rate_cmd_rps: [number, number, number];
    load_factor_cmd: number;
  };
  environment: {
    terrain_reference: number[];
  };
  atmosphere: {
    wind_vector_mps: [number, number, number];
    wind_speed_mps: number;
    density_kgpm3: number;
    turbulence_level: number;
  };
  sensor: {
    quality: number;
    contact_count: number;
  };
  radar: {
    track_ids: string[];
    track_count: number;
  };
  threats: Array<{
    identifier: string;
    position_m: [number, number, number];
    distance_m: number;
  }>;
  derived_metrics: {
    nearest_threat_distance_m: number;
    heading_deg: number;
  };
}

export interface LogFile {
  name: string;
  path: string;
  size_bytes: number;
}

export interface MetricRow {
  episode: number;
  step_count: number;
  mean_return: number;
  mean_length: number;
  rssm_loss: number;
  status: string;
  anomaly?: string;
}

export interface TrainingStatus {
  state: string;
  pid: number | null;
  job_id: string | null;
  episode?: number;
  step_count?: number;
}
