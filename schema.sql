-- CobraQ MySQL schema (utf8mb4)
-- Run once or use init_db() in db.py

CREATE TABLE IF NOT EXISTS users (
  uid VARCHAR(191) PRIMARY KEY,
  email VARCHAR(255) DEFAULT NULL,
  password_hash VARCHAR(255) DEFAULT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  display_name VARCHAR(255) DEFAULT NULL,
  avatar_url LONGTEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_config (
  id INT PRIMARY KEY,
  ai_parse_enabled TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO app_config (id, ai_parse_enabled) VALUES (1, 1);

CREATE TABLE IF NOT EXISTS question_files (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_uid VARCHAR(191) NOT NULL,
  file_id VARCHAR(255) NOT NULL,
  name VARCHAR(500) NOT NULL,
  filename VARCHAR(500) NOT NULL,
  parse_method VARCHAR(64) DEFAULT 'normal',
  uploaded_at VARCHAR(64) NOT NULL,
  file_count INT NOT NULL DEFAULT 0,
  with_answer INT NOT NULL DEFAULT 0,
  UNIQUE KEY uq_user_file (user_uid, file_id),
  KEY idx_user (user_uid),
  CONSTRAINT fk_qf_user FOREIGN KEY (user_uid) REFERENCES users(uid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS questions (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_uid VARCHAR(191) NOT NULL,
  file_id VARCHAR(255) NOT NULL,
  q_id INT NOT NULL,
  question_text LONGTEXT NOT NULL,
  question_rich LONGTEXT,
  choices_json JSON NOT NULL,
  choices_rich JSON,
  answer VARCHAR(16) DEFAULT '',
  explanation TEXT,
  reviewed TINYINT(1) NOT NULL DEFAULT 0,
  reviewed_at DATETIME NULL,
  parse_confidence DECIMAL(5,4) DEFAULT 0,
  parse_flags JSON,
  UNIQUE KEY uq_q (user_uid, file_id, q_id),
  KEY idx_user_file (user_uid, file_id),
  CONSTRAINT fk_q_user FOREIGN KEY (user_uid) REFERENCES users(uid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS quiz_sessions (
  session_id VARCHAR(64) PRIMARY KEY,
  user_uid VARCHAR(191) NOT NULL,
  file_id VARCHAR(255) DEFAULT NULL,
  payload_json JSON NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME DEFAULT NULL,
  KEY idx_user (user_uid),
  CONSTRAINT fk_sess_user FOREIGN KEY (user_uid) REFERENCES users(uid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS quiz_history (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_uid VARCHAR(191) NOT NULL,
  file_id VARCHAR(255) DEFAULT NULL,
  score INT NOT NULL,
  total INT NOT NULL,
  percent INT NOT NULL,
  time_taken INT DEFAULT 0,
  wrong_questions_json JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  date_display VARCHAR(64) NOT NULL,
  KEY idx_user_created (user_uid, created_at),
  CONSTRAINT fk_hist_user FOREIGN KEY (user_uid) REFERENCES users(uid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS revoked_tokens (
  token_hash CHAR(64) PRIMARY KEY,
  token_type VARCHAR(16) NOT NULL,
  user_uid VARCHAR(191) DEFAULT NULL,
  expires_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_revoked_user (user_uid),
  KEY idx_revoked_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
