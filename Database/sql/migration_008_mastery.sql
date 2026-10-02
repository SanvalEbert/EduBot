-- ===========================================================================
-- MIGRAÇÃO 008 (Plano de Execução — D.2): modelo do aluno por competência (BKT).
--
-- O "modelo do aluno" antigo era razão acertos/total com limiar 0.8: sem tempo,
-- sem nº de tentativas, sem esquecimento. `student_mastery` guarda a
-- probabilidade estimada de domínio (p_mastery) por competência, atualizada a
-- cada tentativa por Bayesian Knowledge Tracing e com decaimento por semana sem
-- prática (services/mastery.py). Uma linha por (aluno, competência).
--
-- Após rodar esta migration, reprocesse o histórico de attempts:
--   docker exec -i ova_back_end python -m tools.backfill_mastery
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_008_mastery.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS student_mastery (
    student_id    INT NOT NULL,
    competency_id INT NOT NULL,
    p_mastery     FLOAT NOT NULL DEFAULT 0.2,
    attempts_seen INT NOT NULL DEFAULT 0,
    updated_at    DATETIME NOT NULL,
    PRIMARY KEY (student_id, competency_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id) ON DELETE CASCADE ON UPDATE CASCADE
);
