-- ===========================================================================
-- MIGRAÇÃO 022 (Integração externa): eventos coletados por script em página
-- de terceiro (edubot-tracker.js).
--
-- Até aqui a integração era só de LEITURA (/api/v1, migration_021). Este é o
-- caminho inverso: um material HTML de fora do EduBot (um OVA de parceiro, uma
-- página de teste, e depois o Canvas) inclui o script, que captura cliques e
-- tempo de página e envia para POST /api/v1/collect.
--
-- Por que uma tabela SEPARADA de `learning_events`:
--
--   learning_events exige um aluno do EduBot (FK students) e um verbo do enum
--   fechado — é a matéria-prima do mastery, do painel do tutor e do agente.
--   O material externo não tem login (o visitante é anônimo) e o parceiro
--   escolhe o nome dos próprios eventos ("click", "abriu_video"...). Misturar
--   as duas coisas poluiria as métricas pedagógicas com eventos de teste e
--   obrigaria a inventar alunos. Quando houver identidade real (LTI no Canvas),
--   `user_ref` é a ponte para promover estes eventos a learning_events.
--
--   key_id      qual chave (qual material/parceiro) enviou — é o recorte natural
--               para consultar "o que veio do material do Lucas".
--   visitor_id  id anônimo gerado pelo script e guardado no navegador.
--   session_id  um por carregamento de página.
--   user_ref    id externo do usuário, quando o material souber (opcional).
--   event_type  nome livre validado por regex (click, page_view, page_exit...).
--   target      o que foi clicado (valor de data-edubot-track, id, texto).
--   origin      header Origin da requisição — de qual site o evento veio.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_022_collected_events.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS collected_events (
    event_id     BIGINT PRIMARY KEY AUTO_INCREMENT,
    key_id       INT          NOT NULL,
    event_type   VARCHAR(40)  NOT NULL,
    target       VARCHAR(120) NULL,
    visitor_id   VARCHAR(64)  NOT NULL,
    session_id   VARCHAR(64)  NULL,
    user_ref     VARCHAR(64)  NULL,
    page_url     VARCHAR(500) NULL,
    page_title   VARCHAR(200) NULL,
    context      JSON         NULL,
    origin       VARCHAR(200) NULL,
    occurred_at  DATETIME(6)  NOT NULL,
    received_at  DATETIME(6)  NOT NULL,
    FOREIGN KEY (key_id) REFERENCES api_keys(key_id)
);

-- Consulta típica: "eventos desta chave a partir do cursor X".
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_collected_key ON collected_events(key_id, event_id)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='collected_events' AND INDEX_NAME='idx_collected_key');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- Linha do tempo de um visitante.
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_collected_visitor ON collected_events(visitor_id, occurred_at)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='collected_events' AND INDEX_NAME='idx_collected_visitor');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
