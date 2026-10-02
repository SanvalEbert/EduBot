-- ===========================================================================
-- MIGRAÇÃO 017 (Plano de Execução 2 — E.3): metas semanais.
--
-- Toda segunda-feira o EduBot SUGERE 2 metas do tamanho do aluno (com base na
-- semana anterior + revisões agendadas). O aluno aceita/ajusta; o progresso é
-- atualizado pelos MESMOS sinais do XP (sem telemetria nova). Cumprir concede o
-- XP `meta_semanal`. Uma meta por (aluno, semana, tipo) — o UNIQUE dá
-- idempotência à sugestão.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_017_weekly_goals.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS weekly_goals (
    goal_id    INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    week_start DATE NOT NULL,
    kind       VARCHAR(30) NOT NULL,   -- dias_de_estudo | concluir_modulos | revisoes_em_dia
    target     INT NOT NULL,
    progress   INT NOT NULL DEFAULT 0,
    status     VARCHAR(20) NOT NULL DEFAULT 'sugerida',  -- sugerida|aceita|cumprida|expirada
    created_at DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uc_goal UNIQUE (student_id, week_start, kind),
    INDEX idx_goal_student_week (student_id, week_start)
);
