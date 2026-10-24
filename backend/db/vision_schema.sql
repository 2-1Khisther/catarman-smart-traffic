-- Squad B vision tables (design by Squad B / B4; rows written by Squad A's Node ingest)
-- Open in MySQL Workbench, run it, then use Database > Reverse Engineer for the EER diagram.

CREATE DATABASE IF NOT EXISTS catarman_traffic
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE catarman_traffic;

-- Hourly counts per approach per vehicle class (from vision/density, aggregated)
CREATE TABLE IF NOT EXISTS vehicle_counts (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  intersection_id VARCHAR(16)  NOT NULL DEFAULT 'int01',
  hour_start_utc  DATETIME     NOT NULL,
  approach        ENUM('N','E','S','W') NOT NULL,
  vehicle_class   ENUM('tricycle','motorcycle','car') NOT NULL,
  vehicle_count   INT UNSIGNED NOT NULL DEFAULT 0,
  pcu_total       DECIMAL(10,2) NOT NULL DEFAULT 0,
  UNIQUE KEY uq_hour (intersection_id, hour_start_utc, approach, vehicle_class)
) ENGINE=InnoDB;

-- Red-light violations (from vision/violation). Anonymized: no plate, no body number, no OCR.
CREATE TABLE IF NOT EXISTS violations (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  event_id        VARCHAR(64)  NOT NULL,
  intersection_id VARCHAR(16)  NOT NULL DEFAULT 'int01',
  ts_utc          DATETIME(3)  NOT NULL,
  approach        ENUM('N','E','S','W') NOT NULL,
  vehicle_class   ENUM('tricycle','motorcycle','car') NOT NULL,
  centroid_x      INT UNSIGNED NOT NULL,
  centroid_y      INT UNSIGNED NOT NULL,
  bbox_x1         INT UNSIGNED NOT NULL,
  bbox_y1         INT UNSIGNED NOT NULL,
  bbox_x2         INT UNSIGNED NOT NULL,
  bbox_y2         INT UNSIGNED NOT NULL,
  crop_file       VARCHAR(255) NOT NULL,
  UNIQUE KEY uq_event (event_id),          -- replays never duplicate rows
  KEY idx_ts (ts_utc)
) ENGINE=InnoDB;

-- Vision health log (status changes from vision/heartbeat and vision/status)
CREATE TABLE IF NOT EXISTS vision_health (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  intersection_id VARCHAR(16)  NOT NULL DEFAULT 'int01',
  ts_utc          DATETIME(3)  NOT NULL,
  status          ENUM('OK','DEGRADED','OCCLUDED','ONLINE','OFFLINE') NOT NULL,
  fps             DECIMAL(5,1) NULL,
  conf_avg        DECIMAL(4,3) NULL,
  KEY idx_ts (ts_utc)
) ENGINE=InnoDB;

-- Upsert pattern for the ingest (Squad A):
-- INSERT INTO vehicle_counts (intersection_id, hour_start_utc, approach, vehicle_class, vehicle_count, pcu_total)
-- VALUES (?, ?, ?, ?, ?, ?)
-- ON DUPLICATE KEY UPDATE vehicle_count = vehicle_count + VALUES(vehicle_count),
--                         pcu_total = pcu_total + VALUES(pcu_total);
-- INSERT IGNORE INTO violations (...) VALUES (...);   -- duplicate event_id is skipped
