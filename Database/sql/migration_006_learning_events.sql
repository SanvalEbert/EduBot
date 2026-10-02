-- ===========================================================================
-- MIGRAÇÃO 006 (Plano de Execução — D.1): eventos de aprendizado (xAPI-lite).
--
-- `interactions` mistura tipos enumerados (ova_opened, quiz_submitted) com
-- strings PT livres ("Abriu o assistente do OVA") e NÃO registra o sinal mais
-- rico: tempo de resposta do quiz, play/pause/seek de mídia e as perguntas
-- feitas ao tutor. `learning_events` é o schema unificado (verbo + objeto +
-- contexto JSON) que alimenta o mastery (D.2), a personalização e a auditoria.
--
-- NÃO substitui `interactions` ainda (aposentada numa migration futura, quando
-- D.2/D.3 estiverem estáveis). Por ora as duas convivem e o perfil lê ambas.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_006_learning_events.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS learning_events (
    event_id    BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_id  INT NOT NULL,
    verb        VARCHAR(30) NOT NULL,   -- logged_in|opened|read|played|paused|
                                        -- seeked|completed|answered|asked_tutor|
                                        -- received_intervention|dismissed
    object_type VARCHAR(20) NOT NULL,   -- ova|resource|question|intervention|session
    object_id   INT NULL,
    context     JSON NULL,              -- {perc, seconds, correct, response_ms, text...}
    occurred_at DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Perfil/inatividade por aluno; contagem por verbo (gate de saída da Etapa 3).
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_events_student ON learning_events(student_id, occurred_at)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='learning_events' AND INDEX_NAME='idx_events_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_events_verb ON learning_events(verb, occurred_at)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='learning_events' AND INDEX_NAME='idx_events_verb');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
