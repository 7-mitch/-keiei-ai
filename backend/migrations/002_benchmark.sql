-- ============================================================
-- KEIEI-AI ベンチマーク・評価システム
-- ============================================================

-- ===== チャットフィードバック（👍👎 + レイテンシ）=====
CREATE TABLE IF NOT EXISTS chat_feedbacks (
    id           SERIAL PRIMARY KEY,
    session_id   VARCHAR(100) NOT NULL,
    question     TEXT         NOT NULL,
    answer       TEXT         NOT NULL,
    route        VARCHAR(50)  NOT NULL,
    feedback     VARCHAR(10)  CHECK (feedback IN ('good', 'bad')),
    latency_ms   INTEGER,                          -- 応答時間（ミリ秒）
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ===== LLM-as-Judge 自動採点 =====
CREATE TABLE IF NOT EXISTS chat_benchmarks (
    id              SERIAL PRIMARY KEY,
    feedback_id     INTEGER      REFERENCES chat_feedbacks(id) ON DELETE CASCADE,
    faithfulness    INTEGER      CHECK (faithfulness    BETWEEN 1 AND 5),  -- 事実との一致
    relevancy       INTEGER      CHECK (relevancy       BETWEEN 1 AND 5),  -- 質問への関連性
    completeness    INTEGER      CHECK (completeness    BETWEEN 1 AND 5),  -- 回答の完全性
    business_value  INTEGER      CHECK (business_value  BETWEEN 1 AND 5),  -- ビジネス価値
    routing_correct BOOLEAN,                                                -- ルーティング正誤
    total_score     NUMERIC(3,1),                                           -- 総合スコア
    judge_comment   TEXT,                                                   -- 採点コメント
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedbacks_session  ON chat_feedbacks(session_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_route    ON chat_feedbacks(route);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created  ON chat_feedbacks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_benchmarks_score   ON chat_benchmarks(total_score);