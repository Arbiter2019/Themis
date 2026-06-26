export type Role = "admin" | "labeler";
export type ExperimentStatus = "not_started" | "running" | "completed" | "failed";
export type VariantRole = "control" | "experiment_a" | "experiment_b";

export interface Variant {
  id?: number;
  role: VariantRole;
  name: string;
  description?: string;
  workflow_id: string;
  output_schema: Record<string, unknown>;
  merge_template?: string;
  display_order: number;
}

export interface Experiment {
  id: number;
  uuid: string;
  name: string;
  response_mode: "blocking" | "streaming";
  input_schema: Record<string, unknown>;
  preference_enabled: boolean;
  status: ExperimentStatus;
  total_samples: number;
  executed_samples: number;
  created_by?: string;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  variants?: Variant[];
}

export interface MetricPoint {
  variant_id: number;
  role: VariantRole;
  name: string;
  color: string;
  total: number;
  success_count: number;
  schema_valid_count: number;
  success_rate: number;
  stability_rate: number;
  latency_avg_ms: number | null;
  latency_median_ms: number | null;
  latency_q1_ms: number | null;
  latency_q3_ms: number | null;
}

export interface Report {
  experiment: Experiment;
  metrics: MetricPoint[];
  labeling: null | {
    total: number;
    labeled: number;
    winners: Array<{ variant_id: number; name: string; role: VariantRole; color: string; count: number }>;
  };
}

export interface LabelingExperiment {
  experiment_id: number;
  experiment_uuid: string;
  name: string;
  created_at: string;
  total: number;
  labeled: number;
}

export interface LabelingTask {
  id: number;
  task_uuid: string;
  status: "unlabeled" | "labeled";
  winner_name?: string | null;
  created_at: string;
  labeled_at?: string | null;
}

export interface LabelingTaskDetail {
  id: number;
  task_uuid: string;
  status: "unlabeled" | "labeled";
  items: Array<{
    id: number;
    variant_id: number;
    variant_name: string;
    variant_description?: string | null;
    workflow_id: string;
    merged_output: string;
    display_order: number;
  }>;
}

