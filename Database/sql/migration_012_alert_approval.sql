-- ===========================================================================
-- MIGRAÇÃO 012 (Plano de Execução — B.5): fila de aprovação do tutor.
--
-- Ações de tier alto do agente (alertas de severidade alta, mensagens propostas
-- ao aluno) NÃO saem sozinhas: entram numa fila que o tutor aprova/rejeita. Isso
-- é modelado estendendo `alerts`:
--   status         -> aberto | aguardando_aprovacao | aprovado | rejeitado
--   proposed_action-> JSON da ação a executar na aprovação (ex.: intervenção
--                     assinada "do seu tutor"); NULL = só um alerta informativo
--   decision_id    -> liga à decisão do agente (agent_decisions) p/ a justificativa
--
-- IDEMPOTENTE (só adiciona colunas ausentes). Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_012_alert_approval.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE alerts ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT ''aberto''', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='alerts' AND COLUMN_NAME='status');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE alerts ADD COLUMN proposed_action JSON NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='alerts' AND COLUMN_NAME='proposed_action');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE alerts ADD COLUMN decision_id INT NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='alerts' AND COLUMN_NAME='decision_id');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- Índice para a consulta da fila (por status).
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_alerts_status ON alerts(status)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='alerts' AND INDEX_NAME='idx_alerts_status');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
