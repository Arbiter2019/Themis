CREATE DATABASE IF NOT EXISTS themis
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'themis'@'%' IDENTIFIED BY 'themis_password';
GRANT ALL PRIVILEGES ON themis.* TO 'themis'@'%';
FLUSH PRIVILEGES;

USE themis;

CREATE TABLE IF NOT EXISTS experiments (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  uuid CHAR(36) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  api_key VARCHAR(255) NOT NULL,
  response_mode ENUM('blocking','streaming') NOT NULL DEFAULT 'blocking',
  input_schema JSON NOT NULL,
  preference_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  status ENUM('not_started','running','completed','failed') NOT NULL DEFAULT 'not_started',
  total_samples INT NOT NULL DEFAULT 0,
  executed_samples INT NOT NULL DEFAULT 0,
  created_by VARCHAR(128) NOT NULL,
  created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  completed_at DATETIME(3) NULL,
  INDEX ix_experiments_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS experiment_variants (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  experiment_id BIGINT NOT NULL,
  role ENUM('control','experiment_a','experiment_b') NOT NULL,
  name VARCHAR(100) NOT NULL,
  description VARCHAR(600) NULL,
  workflow_id VARCHAR(150) NOT NULL,
  output_schema JSON NOT NULL,
  merge_template TEXT NULL,
  display_order INT NOT NULL,
  created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  CONSTRAINT fk_variants_experiment FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
  UNIQUE KEY uq_variant_experiment_role (experiment_id, role),
  INDEX ix_variants_experiment_order (experiment_id, display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS experiment_samples (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  experiment_id BIGINT NOT NULL,
  sample_uuid CHAR(36) NOT NULL,
  input_payload JSON NOT NULL,
  created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  CONSTRAINT fk_samples_experiment FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
  UNIQUE KEY uq_sample_experiment_uuid (experiment_id, sample_uuid),
  INDEX ix_samples_experiment_created (experiment_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS variant_runs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  experiment_id BIGINT NOT NULL,
  sample_id BIGINT NOT NULL,
  variant_id BIGINT NOT NULL,
  status ENUM('pending','success','http_error','timeout','dify_error','schema_invalid') NOT NULL,
  http_status INT NULL,
  request_payload JSON NOT NULL,
  response_payload JSON NULL,
  error_message TEXT NULL,
  schema_validation_error JSON NULL,
  latency_ms INT NULL,
  started_at DATETIME(3) NULL,
  finished_at DATETIME(3) NULL,
  created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  CONSTRAINT fk_runs_experiment FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
  CONSTRAINT fk_runs_sample FOREIGN KEY (sample_id) REFERENCES experiment_samples(id) ON DELETE CASCADE,
  CONSTRAINT fk_runs_variant FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE CASCADE,
  UNIQUE KEY uq_run_sample_variant (sample_id, variant_id),
  INDEX ix_runs_experiment_variant_status (experiment_id, variant_id, status),
  INDEX ix_runs_experiment_variant_latency (experiment_id, variant_id, latency_ms)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS labeling_tasks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  experiment_id BIGINT NOT NULL,
  sample_id BIGINT NOT NULL,
  task_uuid CHAR(36) NOT NULL UNIQUE,
  status ENUM('unlabeled','labeled') NOT NULL DEFAULT 'unlabeled',
  created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  labeled_at DATETIME(3) NULL,
  CONSTRAINT fk_label_tasks_experiment FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
  CONSTRAINT fk_label_tasks_sample FOREIGN KEY (sample_id) REFERENCES experiment_samples(id) ON DELETE CASCADE,
  UNIQUE KEY uq_label_task_experiment_sample (experiment_id, sample_id),
  INDEX ix_label_tasks_experiment_status (experiment_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS labeling_task_items (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  variant_id BIGINT NOT NULL,
  merged_output MEDIUMTEXT NOT NULL,
  display_order INT NOT NULL,
  CONSTRAINT fk_label_items_task FOREIGN KEY (task_id) REFERENCES labeling_tasks(id) ON DELETE CASCADE,
  CONSTRAINT fk_label_items_variant FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE CASCADE,
  UNIQUE KEY uq_label_item_task_variant (task_id, variant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS labeling_results (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL UNIQUE,
  selected_variant_id BIGINT NOT NULL,
  labeled_by VARCHAR(128) NOT NULL,
  created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  CONSTRAINT fk_label_results_task FOREIGN KEY (task_id) REFERENCES labeling_tasks(id) ON DELETE CASCADE,
  CONSTRAINT fk_label_results_variant FOREIGN KEY (selected_variant_id) REFERENCES experiment_variants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
