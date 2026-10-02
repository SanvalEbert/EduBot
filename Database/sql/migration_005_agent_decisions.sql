-- ===========================================================================
-- MIGRAÇÃO 005 (Plano de Execução — B.2): trilha de decisões do agente.
--
-- Antes de dar AUTONOMIA ao agente (Etapa 4), dar RASTRO: tudo que o "cérebro"
-- decide — mock incluído — fica registrado. Serve a três coisas de uma vez:
--   1. auditabilidade (LGPD/explicabilidade — a justificativa vai no digest);
--   2. observabilidade (custo/latência por decisão, dashboard do tutor);
--   3. sinal de aprendizado (outcome preenchido depois, B.6).
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_005_agent_decisions.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS agent_decisions (
    decision_id   INT PRIMARY KEY AUTO_INCREMENT,
    student_id    INT,
    trigger_type  VARCHAR(40),      -- quiz_failed | ova_completed | sweep | on_demand | chat | personalized_ova
    input_digest  JSON,             -- digest minimizado do perfil (sem RA/nome completo)
    model_id      VARCHAR(80),
    mock          BOOLEAN,
    tools_called  JSON,             -- [{name, ok}, ...]
    actions       JSON,             -- [{type, id}, ...]
    latency_ms    INT DEFAULT 0,
    input_tokens  INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    outcome       VARCHAR(30) NULL, -- preenchido depois (B.6): aceita|dispensada|expirada|melhorou
    created_at    DATETIME,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Índice para o painel/consulta de custo por período e por aluno.
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_decisions_student ON agent_decisions(student_id, created_at)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='agent_decisions' AND INDEX_NAME='idx_decisions_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_decisions_created ON agent_decisions(created_at)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='agent_decisions' AND INDEX_NAME='idx_decisions_created');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
