-- ===========================================================================
-- MIGRAÇÃO 020 (Plano de Rastreabilidade — Fase 2): leitura por SEÇÃO do OVA.
--
-- Lacuna central da auditoria (P5): o rastreio de leitura era do OVA inteiro —
-- um número de tempo e um de scroll. O professor via QUANTO o aluno leu, nunca
-- ONDE ele travou. Esta tabela guarda, por (aluno, OVA, seção):
--
--   active_seconds   tempo ATIVO na seção (mesmo gate de visibilidade/ociosidade
--                    da leitura: aba oculta ou aluno ausente não contam). Somado
--                    por delta no servidor, como o read_time.
--   max_scroll_perc  marca d'água de quanto da seção foi percorrido.
--   visits           quantas vezes o aluno ENTROU na seção; > 1 indica releitura
--                    (sinal de dificuldade — ou de revisão deliberada).
--
-- `section_id` é o id da seção no HTML do OVA (fonte estável, versionada no
-- repositório) — ver services/ovaContent.ts. Seções renomeadas deixam histórico
-- órfão, que é dado histórico legítimo e simplesmente não aparece no painel.
--
-- Invariante de auditoria: SUM(active_seconds) das seções <= ova_progress.read_time
-- (a diferença é o tempo fora de qualquer seção: hero, mídias, quiz).
--
-- IDEMPOTENTE. Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_020_ova_section_progress.sql
-- ===========================================================================
USE ova_db;

CREATE TABLE IF NOT EXISTS ova_section_progress (
    section_progress_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id      INT NOT NULL,
    ova_id          INT NOT NULL,
    section_id      VARCHAR(120) NOT NULL,
    section_index   INT NOT NULL DEFAULT 0,
    active_seconds  INT NOT NULL DEFAULT 0,
    max_scroll_perc INT NOT NULL DEFAULT 0,
    visits          INT NOT NULL DEFAULT 0,
    last_access     DATETIME NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (ova_id) REFERENCES ovas(ova_id) ON DELETE CASCADE ON UPDATE CASCADE,
    -- uma linha por (aluno, OVA, seção) — a rota faz upsert somando deltas
    CONSTRAINT uc_ova_section UNIQUE (student_id, ova_id, section_id)
);

-- Painel do professor: "onde a turma trava neste OVA" varre por OVA+seção.
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'CREATE INDEX idx_section_ova ON ova_section_progress(ova_id, section_index)', 'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='ova_section_progress' AND INDEX_NAME='idx_section_ova');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
