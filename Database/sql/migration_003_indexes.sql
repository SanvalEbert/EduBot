-- ===========================================================================
-- MIGRAÇÃO 003 (Plano de Execução — A.2): índices secundários.
--
-- O schema não tinha nenhum índice além das PKs/uniques. As queries agregadas
-- do perfil (A.1), da inatividade, do quiz e do agente filtravam por colunas
-- sem índice (full scan) — irrelevante na demo, letal com turmas reais.
--
-- Esta migração cria os índices que sustentam os filtros mais quentes. É
-- IDEMPOTENTE: cada CREATE INDEX é guardado por information_schema.STATISTICS
-- (MySQL não tem CREATE INDEX IF NOT EXISTS). Roda num banco novo (entra no init
-- do Docker, ordem alfabética após dml_extra.sql) ou num volume EXISTENTE:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_003_indexes.sql
-- ===========================================================================
USE ova_db;

-- ---------------------------------------------------------------------------
-- Macro idempotente: cria o índice só se ainda não existir.
-- (Repetimos o bloco por índice porque o MySQL não permite CREATE INDEX IF NOT
--  EXISTS nem laços fora de stored procedures.)
-- ---------------------------------------------------------------------------

-- attempts: perfil, inatividade, mastery futura (D.2) — por aluno/tempo
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_attempts_student ON attempts(student_id, attempt_time)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='attempts' AND INDEX_NAME='idx_attempts_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- attempts: agregação por questão (JOIN Questions -> competência/OVA)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_attempts_question ON attempts(question_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='attempts' AND INDEX_NAME='idx_attempts_question');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- answers: acertos por aluno (uc_answers já cobre o par student+question, mas
-- um índice por student ajuda os LEFT JOIN do perfil)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_answers_student ON answers(student_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='answers' AND INDEX_NAME='idx_answers_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- interactions: inatividade (MAX interaction_date por aluno)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_interactions_student ON interactions(student_id, interaction_date)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='interactions' AND INDEX_NAME='idx_interactions_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- questions: quiz e tools do agente (por competência)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_questions_competency ON questions(competency_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='questions' AND INDEX_NAME='idx_questions_competency');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- questions: questões por OVA (quiz do módulo)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_questions_ova ON questions(ova_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='questions' AND INDEX_NAME='idx_questions_ova');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- resources: recursos por OVA (perfil) e por competência (remediação do agente)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_resources_ova ON resources(ova_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resources' AND INDEX_NAME='idx_resources_ova');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_resources_competency ON resources(competency_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resources' AND INDEX_NAME='idx_resources_competency');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- interventions: dedup diária (proatividade) e inbox do aluno
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_interventions_student ON interventions(student_id, date, result)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='interventions' AND INDEX_NAME='idx_interventions_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- alerts: dedup por (aluno, lido) e contagem do painel do tutor
-- (`read` é palavra reservada — sempre com crase)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_alerts_student ON alerts(student_id, `read`)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='alerts' AND INDEX_NAME='idx_alerts_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- ova_progress: "continuar de onde parou" (U.4) — última atividade por aluno
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_ovaprogress_student ON ova_progress(student_id, last_access)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='ova_progress' AND INDEX_NAME='idx_ovaprogress_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- resource_progress: consumo por aluno (perfil)
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_resourceprogress_student ON resource_progress(student_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND INDEX_NAME='idx_resourceprogress_student');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
