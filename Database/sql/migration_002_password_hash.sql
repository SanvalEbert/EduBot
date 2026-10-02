-- ===========================================================================
-- MIGRAÇÃO 002 (Fase 4d — A5): suporte a senhas com hash.
--
-- O mecanismo de senha em texto plano (varchar(30) + comparação direta) foi
-- substituído por PBKDF2-HMAC-SHA256 com salt por usuário. O hash armazenado
-- ("pbkdf2_sha256$<iter>$<salt>$<hash>") tem ~118 caracteres — a coluna
-- precisa ser alargada.
--
-- As senhas do seed permanecem em texto plano no banco e são convertidas para
-- hash automaticamente no PRIMEIRO login de cada aluno (upgrade-on-login em
-- loginRoute.py) — nenhuma senha precisa ser redefinida.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_002_password_hash.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(CHARACTER_MAXIMUM_LENGTH < 255,
  'ALTER TABLE students MODIFY COLUMN student_password VARCHAR(255)', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'ova_db' AND TABLE_NAME = 'students'
    AND COLUMN_NAME = 'student_password');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
