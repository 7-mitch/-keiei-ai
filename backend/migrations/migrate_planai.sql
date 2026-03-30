CREATE TABLE IF NOT EXISTS projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    status      VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase       INTEGER NOT NULL DEFAULT 1 CHECK (phase IN (1, 2, 3)),
    name        VARCHAR(200) NOT NULL,
    assign      VARCHAR(100),
    status      VARCHAR(20) DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'done', 'risk')),
    progress    INTEGER DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    start_date  DATE,
    end_date    DATE,
    color       VARCHAR(20) DEFAULT 'blue',
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);
CREATE TABLE IF NOT EXISTS project_members (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    role        VARCHAR(100),
    skills      TEXT[] DEFAULT '{}',
    workload    INTEGER DEFAULT 0 CHECK (workload BETWEEN 0 AND 200),
    UNIQUE (project_id, name)
);
CREATE INDEX IF NOT EXISTS idx_tasks_project   ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status    ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_end_date  ON tasks(end_date);
CREATE INDEX IF NOT EXISTS idx_members_project ON project_members(project_id);
