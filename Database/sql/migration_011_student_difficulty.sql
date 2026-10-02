-- ===========================================================================
-- MIGRAÇÃO 011 (Plano de Execução — B.5): dificuldade por aluno × competência.
--
-- A tool `ajustar_dificuldade` (e o tutor) podem sobrepor o nível-alvo de uma
-- competência para um aluno específico. `/question/ova` passa a servir o pool
-- filtrado por esse nível (zona proximal) quando há override; sem override, cai
-- na regra por domínio (D.4). Teto de 1 mudança/dia (validado na tool).
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_011_student_difficulty.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS student_difficulty (
    student_id    INT NOT NULL,
    competency_id INT NOT NULL,
    level         TINYINT NOT NULL DEFAULT 2,   -- 1 fácil · 2 média · 3 difícil
    updated_at    DATETIME NOT NULL,
    PRIMARY KEY (student_id, competency_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id) ON DELETE CASCADE ON UPDATE CASCADE
);
