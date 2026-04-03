-- ============================================================
-- KEIEI-AI データベーススキーマ
-- 初回セットアップは /setup から実施
-- デフォルトユーザーは作成しない（セキュリティ上）
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(100),
    role          VARCHAR(20)  NOT NULL DEFAULT 'operator'
                  CHECK (role IN ('executive', 'manager', 'operator')),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER        REFERENCES users(id) ON DELETE CASCADE,
    name       VARCHAR(200)   NOT NULL,
    account_no VARCHAR(50),
    balance    NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id               SERIAL PRIMARY KEY,
    account_id       INTEGER        NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    amount           NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    transaction_type VARCHAR(20)    NOT NULL CHECK (transaction_type IN ('credit', 'debit')),
    description      TEXT,
    is_flagged       BOOLEAN        NOT NULL DEFAULT FALSE,
    flag_reason      TEXT,
    risk_score       NUMERIC(5, 4)  CHECK (risk_score BETWEEN 0 AND 1),
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fraud_alerts (
    id             SERIAL PRIMARY KEY,
    transaction_id INTEGER     REFERENCES transactions(id) ON DELETE SET NULL,
    account_id     INTEGER     REFERENCES accounts(id)    ON DELETE SET NULL,
    alert_type     VARCHAR(50) NOT NULL DEFAULT 'multi_layer_detection',
    severity       VARCHAR(20) NOT NULL DEFAULT 'low'
                   CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description    TEXT,
    ai_reasoning   TEXT,
    status         VARCHAR(20) NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'resolved', 'false_positive')),
    resolved_by    INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    resolved_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            SERIAL PRIMARY KEY,
    operator_id   INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    operator_type VARCHAR(50),
    target_type   VARCHAR(50),
    target_id     INTEGER,
    action        VARCHAR(100) NOT NULL,
    before_value  JSONB,
    after_value   JSONB,
    ai_confidence NUMERIC(5, 4) CHECK (ai_confidence BETWEEN 0 AND 1),
    session_id    VARCHAR(100),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS web_collection_logs (
    id           SERIAL PRIMARY KEY,
    url          TEXT        NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'success'
                 CHECK (status IN ('success', 'failed')),
    data_type    VARCHAR(50),
    raw_content  TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS aptitude_results (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER     NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    scores     JSONB       NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    status      VARCHAR(20)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived')),
    created_by  INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase       INTEGER      NOT NULL DEFAULT 1 CHECK (phase IN (1, 2, 3)),
    name        VARCHAR(200) NOT NULL,
    assign      VARCHAR(100),
    status      VARCHAR(20)  NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'doing', 'done', 'risk')),
    progress    INTEGER      NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    start_date  DATE,
    end_date    DATE,
    color       VARCHAR(20)  NOT NULL DEFAULT 'blue',
    note        TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_dates CHECK (
        end_date IS NULL OR start_date IS NULL OR end_date >= start_date
    )
);

CREATE TABLE IF NOT EXISTS project_members (
    id         SERIAL PRIMARY KEY,
    project_id INTEGER      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name       VARCHAR(100) NOT NULL,
    role       VARCHAR(100),
    skills     TEXT[]       NOT NULL DEFAULT '{}',
    workload   INTEGER      NOT NULL DEFAULT 0 CHECK (workload BETWEEN 0 AND 200),
    UNIQUE (project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_users_email           ON users(email);
CREATE INDEX IF NOT EXISTS idx_accounts_user         ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account  ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created  ON transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_flagged  ON transactions(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_status   ON fraud_alerts(status);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_severity ON fraud_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created    ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_logs_status       ON web_collection_logs(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project         ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status          ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_end_date        ON tasks(end_date);
CREATE INDEX IF NOT EXISTS idx_members_project       ON project_members(project_id);