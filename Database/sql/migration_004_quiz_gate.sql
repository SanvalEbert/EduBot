-- ===========================================================================
-- MIGRAÇÃO 004 (Plano de Execução — U.1): regra de liberação do quiz.
--
-- O quiz global (aba solta) liberava qualquer quiz a qualquer momento, sem
-- relação com o consumo do conteúdo — pedagogia invertida e, pior, o dado que
-- alimenta o agente nascia contaminado (aluno "erra tudo" sem ter lido nada).
--
-- Esta coluna define o % mínimo de leitura do OVA para liberar o quiz do módulo.
-- Default 70. `0` = sem gate (conteúdo introdutório/curto). A liberação é
-- validada NO BACKEND (/question/ova e /question/answer) — esconder o botão no
-- front não impede curl.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_004_quiz_gate.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE ovas ADD COLUMN quiz_gate_perc INT NOT NULL DEFAULT 70', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='ovas' AND COLUMN_NAME='quiz_gate_perc');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
