-- ===========================================================================
-- MIGRAÇÃO 019 (Plano de Rastreabilidade — Fase 1): consumo REAL de vídeo.
--
-- Problema que ela corrige (auditoria P2): `perc_consumed` era a POSIÇÃO máxima
-- do player (checkpoints de 10%) e `seconds_consumed` recebia a posição, não o
-- tempo assistido. Um seek para o fim marcava 100% sem o aluno ver nada — a
-- métrica mentia. Agora são três medidas independentes:
--
--   watched_seconds        segundos REAIS assistidos (só com o vídeo tocando E a
--                          aba visível). Replay conta — é consumo de verdade.
--   coverage_bitmap        100 baldes de 1% da linha do tempo ('0'/'1'); um
--                          balde só marca com reprodução passando por ele, então
--                          seek NÃO preenche. O cliente manda o bitmap
--                          ACUMULADO da sessão e o servidor faz OR (auto-heal:
--                          um OR perdido por corrida volta no próximo sync).
--   coverage_perc          baldes marcados (0..100) — materializado no upsert.
--                          É esta métrica que passa a definir a conclusão.
--   last/max_position_*    retomada e ponto de ABANDONO (onde a turma larga).
--   playback_rate_last     última velocidade de reprodução observada.
--
-- `perc_consumed`/`seconds_consumed` permanecem intactas (leitura legada e
-- áudio/atividade continuam usando-as) — degradação segura.
--
-- IDEMPOTENTE (só adiciona a coluna que ainda não existir). Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_019_video_tracking.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resource_progress ADD COLUMN watched_seconds INT NOT NULL DEFAULT 0', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND COLUMN_NAME='watched_seconds');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resource_progress ADD COLUMN coverage_bitmap VARCHAR(100) NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND COLUMN_NAME='coverage_bitmap');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resource_progress ADD COLUMN coverage_perc INT NOT NULL DEFAULT 0', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND COLUMN_NAME='coverage_perc');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resource_progress ADD COLUMN last_position_seconds INT NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND COLUMN_NAME='last_position_seconds');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resource_progress ADD COLUMN max_position_seconds INT NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND COLUMN_NAME='max_position_seconds');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resource_progress ADD COLUMN playback_rate_last DECIMAL(3,2) NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='resource_progress' AND COLUMN_NAME='playback_rate_last');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
