-- ===========================================================================
-- MIGRAÇÃO 014 (Plano de Execução 2 — H.1): histórico diário de domínio.
--
-- `student_mastery` guarda o domínio ATUAL (BKT). Para ILUSTRAR a evolução do
-- aluno (setas de tendência na teia de competências, "você subiu 12% em Lógica
-- nesta semana" — Etapa 8/G.5) é preciso um snapshot por dia. O sweep diário
-- grava uma linha por (aluno, competência) com o p_mastery daquele dia.
--
-- Uma linha por (aluno, competência, data). O PK composto dá idempotência: rodar
-- o sweep 2× no mesmo dia não duplica (INSERT ... ON DUPLICATE KEY / IGNORE).
--
-- 013 permanece RESERVADA para avatar_licenses (Etapa 6/V.4, futura).
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_014_mastery_history.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS student_mastery_history (
    student_id    INT NOT NULL,
    competency_id INT NOT NULL,
    snapshot_date DATE NOT NULL,
    p_mastery     FLOAT NOT NULL,
    PRIMARY KEY (student_id, competency_id, snapshot_date),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Tendência por aluno: "meus últimos 7 dias" (a rota /mastery/trend).
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_mastery_hist_student ON student_mastery_history(student_id, snapshot_date)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='student_mastery_history' AND INDEX_NAME='idx_mastery_hist_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
