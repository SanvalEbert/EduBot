-- ===========================================================================
-- MIGRAÇÃO 010 (Plano de Execução — D.4): dificuldade por questão.
--
-- O quiz servia sempre TODAS as questões, sem noção de nível. Com `difficulty`
-- (1 fácil · 2 média · 3 difícil) o pool de /question/ova passa a ser adaptativo:
-- casado com o domínio (D.2) da competência, entrega a "zona proximal" (fáceis
-- primeiro; difíceis só quando o aluno já domina). Também dá efeito real à tool
-- `ajustar_dificuldade` (B.5).
--
-- Default 2 (média) — seguro para as questões existentes. Calibre depois com
-- o job one-off (proporção de erro histórica):
--   docker exec ova_back_end python -m tools.calibrate_difficulty
--
-- IDEMPOTENTE (só adiciona a coluna se ainda não existir). Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_010_difficulty.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE questions ADD COLUMN difficulty TINYINT NOT NULL DEFAULT 2', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='questions' AND COLUMN_NAME='difficulty');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
