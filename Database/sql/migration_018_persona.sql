-- ===========================================================================
-- MIGRAÇÃO 018 (Plano de Execução 3 — AV.2): persona do avatar por aluno.
--
--   persona   personagem escolhido como companheiro de estudo
--             ('edubot' | 'einstein' | 'curie'). Antes vivia só no localStorage
--             (não seguia o aluno entre dispositivos e o tutor IA não sabia qual
--             persona "fala"). Agora é atributo do aluno, servido em
--             GET /student/me e gravado por POST /student/persona.
--             Default 'edubot' (mascote da plataforma).
--
-- IDEMPOTENTE (só adiciona a coluna se ausente). Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_018_persona.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE students ADD COLUMN persona VARCHAR(24) NOT NULL DEFAULT ''edubot''', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='students' AND COLUMN_NAME='persona');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
