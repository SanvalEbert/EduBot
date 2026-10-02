-- ===========================================================================
-- MIGRAÇÃO 007 (Plano de Execução — D.5): consentimento (LGPD).
--
-- Base legal estruturada para o tratamento de dados do aluno. Três finalidades:
--   tracking_pedagogico  -> execução do contrato educacional (informado, não
--                           opcional): registrar consumo/desempenho é o serviço;
--   ia_sobre_dados       -> opt-in revogável: usar LLM sobre os dados do aluno e
--                           guardar o texto das perguntas ao tutor;
--   imagem_voz           -> opt-in revogável: virtualização de personagem/voz.
--
-- UNIQUE (student_id, purpose): uma linha por finalidade por aluno (upsert de
-- granted/revoked). O ON DELETE CASCADE dá a base para a exclusão efetiva (a
-- solicitação vira alerta de admin; o admin executa o DELETE do aluno).
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_007_consents.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS consents (
    consent_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    purpose    VARCHAR(40) NOT NULL,   -- tracking_pedagogico | ia_sobre_dados | imagem_voz
    granted    BOOLEAN NOT NULL,
    granted_at DATETIME NOT NULL,
    revoked_at DATETIME NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uc_consent UNIQUE (student_id, purpose)
);
