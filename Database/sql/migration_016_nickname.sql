-- ===========================================================================
-- MIGRAÇÃO 016 (Plano de Execução 2 — G.4/R.2): apelido e título do aluno.
--
--   nickname  apelido público no ranking da turma (G.4). O ranking é OPT-IN
--             (consentimento 'ranking_turma') e o apelido é obrigatório para
--             participar — quem não participa nunca é listado pelo nome real.
--   title     título ativo escolhido pelo aluno entre os que suas conquistas
--             concedem ("Revisor Pontual", "Mestre em Lógica") — Etapa 9/R.2.
--             Já entra aqui para não fragmentar a migration da tabela students.
--
-- IDEMPOTENTE (só adiciona colunas ausentes). Volume MySQL existente:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_016_nickname.sql
-- ===========================================================================
USE ova_db;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE students ADD COLUMN nickname VARCHAR(40) NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='students' AND COLUMN_NAME='nickname');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE students ADD COLUMN title VARCHAR(40) NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='ova_db' AND TABLE_NAME='students' AND COLUMN_NAME='title');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
