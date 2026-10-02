-- ===========================================================================
-- MIGRAÇÃO 015 (Plano de Execução 2 — G.1/G.2/G.3): gamificação núcleo.
--
-- Três tabelas, todas por aluno:
--   xp_events            trilha de XP server-side (fonte da verdade do total e do
--                        ranking). O XP mede ESFORÇO (concluir, revisar em dia,
--                        voltar amanhã) — nunca nota. Anti-farm: o par
--                        (aluno, regra, objeto, dia) é único (dedup); regras com
--                        teto diário são limitadas no serviço.
--   student_streak       sequência de dias de estudo, com "escudo" semanal (1
--                        folga não quebra a chama). Perder a sequência ZERA o
--                        contador, nunca tira XP já ganho.
--   student_achievements conquistas desbloqueadas (o catálogo vive no código).
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_015_gamification.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS xp_events (
    xp_event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_id  INT NOT NULL,
    rule        VARCHAR(40) NOT NULL,     -- modulo_concluido|quiz_do_modulo|
                                          -- revisao_em_dia|dia_de_estudo|
                                          -- pergunta_ao_tutor|meta_semanal|desafio_tentado
    object_type VARCHAR(20) NULL,         -- ova|question|competency|session|goal
    object_id   INT NULL,
    points      INT NOT NULL,
    awarded_on  DATE NOT NULL,
    created_at  DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    -- dedup do MESMO ganho no MESMO dia (backstop de corrida). NULLs em
    -- object_id não são únicos em MySQL/SQLite — regras sem objeto são
    -- deduplicadas no serviço (gamification.award).
    CONSTRAINT uc_xp UNIQUE (student_id, rule, object_type, object_id, awarded_on),
    INDEX idx_xp_student_day (student_id, awarded_on)
);

CREATE TABLE IF NOT EXISTS student_streak (
    student_id         INT PRIMARY KEY,
    current_days       INT NOT NULL DEFAULT 0,
    best_days          INT NOT NULL DEFAULT 0,
    last_activity_date DATE NULL,
    shield_used_on     DATE NULL,         -- último uso do escudo (1 por semana ISO)
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS student_achievements (
    student_id     INT NOT NULL,
    achievement_id VARCHAR(40) NOT NULL,  -- id do catálogo (services/gamification.py)
    unlocked_at    DATETIME NOT NULL,
    PRIMARY KEY (student_id, achievement_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE
);
