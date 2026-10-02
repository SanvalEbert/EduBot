-- ===========================================================================
-- MIGRAÇÃO 021 (Integração externa): chaves de API para sistemas parceiros.
--
-- O EduBot só sabia autenticar ALUNO (token HMAC de sessão, 7 dias, emitido no
-- /login — ver api/auth.py). Não havia como um SISTEMA externo (o app PHP de um
-- parceiro, um BI, um piloto de pesquisa) ler dados sem que alguém entregasse a
-- senha de um aluno ou — pior — a credencial do MySQL.
--
-- Esta tabela é a credencial de MÁQUINA:
--
--   key_hash    SHA-256 do segredo. A chave em claro é mostrada UMA vez, na
--               criação, e nunca mais: vazar o banco não vaza as chaves.
--   key_prefix  os 8 primeiros caracteres do segredo, em claro. Serve só para
--               identificar a linha em log/painel ("ek_live_3f9a…") sem ter o
--               segredo — e para achar a linha a revogar.
--   scopes      CSV de escopos concedidos. Sem escopo casado, o endpoint devolve
--               403 mesmo com a chave válida. O escopo `students:pii` é o único
--               que libera nome/RA do aluno e é deliberadamente separado dos
--               demais: abrir catálogo ou rastreio NÃO abre dado pessoal junto.
--   active      revogação é UPDATE active=0, não DELETE — a trilha de quem teve
--               acesso e até quando é exigência de auditoria (LGPD art. 37).
--   last_used_at / request_count  uso observado, para detectar chave esquecida
--               ativa e para o relatório de acesso a dado pessoal.
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_021_api_keys.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS api_keys (
    key_id        INT PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(100) NOT NULL,    -- quem é o parceiro ("Piloto UFBA")
    key_prefix    VARCHAR(16)  NOT NULL,    -- em claro, só para identificar
    key_hash      CHAR(64)     NOT NULL,    -- SHA-256 hex do segredo completo
    scopes        VARCHAR(255) NOT NULL DEFAULT '',  -- CSV: catalog:read,tracking:read,...
    active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    DATETIME     NOT NULL,
    expires_at    DATETIME     NULL,        -- NULL = sem validade definida
    last_used_at  DATETIME     NULL,
    request_count INT          NOT NULL DEFAULT 0,
    notes         VARCHAR(255) NULL         -- contato do parceiro, nº do processo
);

-- O lookup do request quente é por hash (a chave chega inteira no header e é
-- hasheada antes da busca). UNIQUE também impede cadastrar a mesma chave 2x.
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE UNIQUE INDEX idx_api_keys_hash ON api_keys(key_hash)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='api_keys' AND INDEX_NAME='idx_api_keys_hash');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='api_keys' AND INDEX_NAME='idx_api_keys_prefix');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
