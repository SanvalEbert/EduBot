-- ===========================================================================
-- MIGRAÇÃO 009 (Plano de Execução — D.3): revisão espaçada (SM-2 simplificado).
--
-- Domínio (D.2) sem revisão decai (esquecimento). `review_schedule` agenda a
-- revisão de cada competência por aluno: ao acertar na data, o intervalo cresce
-- (× ease, teto 60d); ao errar, volta a 1 dia. O sweep diário marca vencidas e
-- cria a intervenção "hora de revisar X". Uma linha por (aluno, competência,
-- data de vencimento) — o UNIQUE dá idempotência ao reagendar.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_009_reviews.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS review_schedule (
    review_id     INT PRIMARY KEY AUTO_INCREMENT,
    student_id    INT NOT NULL,
    competency_id INT NOT NULL,
    due_date      DATE NOT NULL,
    interval_days INT NOT NULL DEFAULT 1,
    ease          FLOAT NOT NULL DEFAULT 2.5,
    status        VARCHAR(20) NOT NULL DEFAULT 'agendada',  -- agendada|vencida|cumprida|cancelada
    created_by    VARCHAR(20) NOT NULL DEFAULT 'agent',     -- agent|rule|tutor
    created_at    DATETIME NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uc_review UNIQUE (student_id, competency_id, due_date)
);

-- Varredura do sweep: "o que vence hoje/está vencido".
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_review_due ON review_schedule(due_date, status)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='review_schedule' AND INDEX_NAME='idx_review_due');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
