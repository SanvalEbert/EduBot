-- ===========================================================================
-- Usuário MySQL SOMENTE-LEITURA para a integração PHP (Caminho B).
--
-- NÃO roda automaticamente: este arquivo fica fora do /docker-entrypoint-initdb.d
-- de propósito, porque contém uma senha que VOCÊ precisa trocar antes de aplicar.
--
--   1. troque 'TROQUE-ESTA-SENHA' abaixo por uma senha forte
--   2. docker exec -i ova_db mysql -uroot -pPassword-1 < Database/sql/usuario_somente_leitura.sql
--   3. use a mesma senha em integracoes/php/config.local.php
--
-- Por que um usuário separado, e não o `eduardo`:
--
--   O `eduardo` é a credencial da APLICAÇÃO — tem INSERT/UPDATE/DELETE porque o
--   Flask grava progresso, eventos e tentativas. Um script de leitura que
--   carregue essa credencial transforma qualquer falha sua (injeção, arquivo
--   exposto, log com a senha) em capacidade de ESCRITA sobre a base inteira.
--   Com SELECT apenas, o pior caso vira leitura indevida — grave, mas
--   recuperável, e sem corromper o histórico de aprendizagem dos alunos.
--
-- GRANT por TABELA, e não `GRANT SELECT ON ova_db.*`:
--
--   Tabela nova que apareça numa migration futura NÃO fica visível sozinha para
--   o parceiro. Expor passa a ser uma decisão consciente (acrescentar a linha
--   aqui), não o padrão. Note que `students` está de fora por isso mesmo — veja
--   o bloco comentado no fim.
-- ===========================================================================

CREATE USER IF NOT EXISTS 'edubot_leitura'@'%' IDENTIFIED BY 'TROQUE-ESTA-SENHA';

-- Catálogo (conteúdo, sem dado pessoal)
GRANT SELECT ON ova_db.courses             TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.course_subjects     TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.offerings           TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.competencies        TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.ovas                TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.questions           TO 'edubot_leitura'@'%';

-- Rastreio e desempenho (dado de aluno — sai pseudonimizado pelo api.php)
GRANT SELECT ON ova_db.learning_events     TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.ova_progress        TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.ova_section_progress TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.attempts            TO 'edubot_leitura'@'%';
GRANT SELECT ON ova_db.student_mastery     TO 'edubot_leitura'@'%';

-- ---------------------------------------------------------------------------
-- ALUNOS — dado pessoal (LGPD). Duas formas, escolha UMA.
-- ---------------------------------------------------------------------------

-- (a) PADRÃO — sem nome nem RA. O api.php consegue listar alunos e montar
--     coortes, mas não consegue identificar ninguém, porque as colunas
--     `student_name` e `ra` simplesmente não estão no GRANT. É o banco
--     impondo o limite, não o código: um bug no PHP não tem como furar isso.
GRANT SELECT (student_id, course_id, role, is_admin, persona, nickname)
      ON ova_db.students TO 'edubot_leitura'@'%';

-- (b) COM dado pessoal. Descomente SOMENTE com base legal registrada (contrato,
--     termo de consentimento ou finalidade de pesquisa aprovada). `student_password`
--     continua fora em qualquer cenário.
-- GRANT SELECT (student_id, ra, student_name, course_id, role, is_admin, persona, nickname)
--       ON ova_db.students TO 'edubot_leitura'@'%';

FLUSH PRIVILEGES;

-- Conferência (deve listar apenas SELECT):
--   SHOW GRANTS FOR 'edubot_leitura'@'%';
