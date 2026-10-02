-- ===========================================================================
-- MIGRAÇÃO 001 (Fase 4 — A12): i18n de CONTEÚDO no banco.
--
-- Adiciona colunas de tradução (EN) para o conteúdo semeado — nomes de OVA,
-- competências, títulos de recursos e questões do quiz — e as popula. A API
-- passa a servir o conteúdo conforme `lang`; o dicionário manual do frontend
-- (contentDict.ts) morre.
--
-- IDEMPOTENTE: pode rodar num banco novo (entra no init do Docker, ordem
-- alfabética após dml_extra.sql) ou num volume MySQL EXISTENTE:
--   docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
--     < Database/sql/migration_001_i18n.sql
-- Os ALTERs são guardados por information_schema (MySQL não tem ADD COLUMN IF
-- NOT EXISTS); os UPDATEs são naturalmente reexecutáveis.
-- ===========================================================================
USE ova_db;

-- ---------------------------------------------------------------------------
-- 1. Colunas de tradução (ALTER idempotente via prepared statement)
-- ---------------------------------------------------------------------------
SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE ovas ADD COLUMN ova_name_en TEXT NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'ova_db' AND TABLE_NAME = 'ovas' AND COLUMN_NAME = 'ova_name_en');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE competencies ADD COLUMN competency_description_en TEXT NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'ova_db' AND TABLE_NAME = 'competencies' AND COLUMN_NAME = 'competency_description_en');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE resources ADD COLUMN resource_title_en VARCHAR(255) NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'ova_db' AND TABLE_NAME = 'resources' AND COLUMN_NAME = 'resource_title_en');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE questions ADD COLUMN statement_en TEXT NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'ova_db' AND TABLE_NAME = 'questions' AND COLUMN_NAME = 'statement_en');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE questions ADD COLUMN alternatives_en JSON NULL', 'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'ova_db' AND TABLE_NAME = 'questions' AND COLUMN_NAME = 'alternatives_en');
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

-- ---------------------------------------------------------------------------
-- 2. OVAs
-- ---------------------------------------------------------------------------
UPDATE ovas SET ova_name_en = 'Quantum Computing'             WHERE ova_id = 1;
UPDATE ovas SET ova_name_en = 'Calculus'                      WHERE ova_id = 2;
UPDATE ovas SET ova_name_en = 'Calculus 2'                    WHERE ova_id = 3;
UPDATE ovas SET ova_name_en = 'Cloud Computing Fundamentals'  WHERE ova_id = 4;

-- ---------------------------------------------------------------------------
-- 3. Competências
-- ---------------------------------------------------------------------------
UPDATE competencies SET competency_description_en = 'Understand the fundamental principles of quantum computing' WHERE competency_id = 1;
UPDATE competencies SET competency_description_en = 'Analyze the applications of quantum computing' WHERE competency_id = 2;
UPDATE competencies SET competency_description_en = 'Recognize the technical challenges and limitations of quantum computing' WHERE competency_id = 3;
UPDATE competencies SET competency_description_en = 'Compute derivatives and integrals of polynomial and trigonometric functions' WHERE competency_id = 4;
UPDATE competencies SET competency_description_en = 'Apply limit concepts to simple functions, including identifying behavior at infinity' WHERE competency_id = 5;
UPDATE competencies SET competency_description_en = 'Identify maximum and minimum points of functions using differential calculus for curve analysis' WHERE competency_id = 6;
UPDATE competencies SET competency_description_en = 'Understand cloud computing service models (IaaS, PaaS, SaaS)' WHERE competency_id = 7;
UPDATE competencies SET competency_description_en = 'Distinguish deployment models: public, private and hybrid cloud' WHERE competency_id = 8;
UPDATE competencies SET competency_description_en = 'Recognize the economic benefits and security challenges of the cloud' WHERE competency_id = 9;

-- ---------------------------------------------------------------------------
-- 4. Recursos (títulos)
-- ---------------------------------------------------------------------------
UPDATE resources SET resource_title_en = 'Reading: The Quantum Journey' WHERE resource_id = 1;
UPDATE resources SET resource_title_en = 'Video: Introduction to Quantum Computing' WHERE resource_id = 2;
UPDATE resources SET resource_title_en = 'Video: Qubits and Superposition' WHERE resource_id = 3;
UPDATE resources SET resource_title_en = 'Podcast: Quantum Talks (ep. 1)' WHERE resource_id = 4;
UPDATE resources SET resource_title_en = 'Quiz: Quantum Computing' WHERE resource_id = 5;
UPDATE resources SET resource_title_en = 'Practical activity: simulate a qubit in the IBM Quantum Composer' WHERE resource_id = 6;
UPDATE resources SET resource_title_en = 'Reading: Limits and Derivatives' WHERE resource_id = 7;
UPDATE resources SET resource_title_en = 'Video: The essence of Calculus' WHERE resource_id = 8;
UPDATE resources SET resource_title_en = 'Podcast: Calculus in everyday life (ep. 1)' WHERE resource_id = 9;
UPDATE resources SET resource_title_en = 'Quiz: Calculus' WHERE resource_id = 10;
UPDATE resources SET resource_title_en = 'Practical activity: solve the limits worksheet and submit to the teacher' WHERE resource_id = 11;
UPDATE resources SET resource_title_en = 'Reading: Integrals and Applications' WHERE resource_id = 12;
UPDATE resources SET resource_title_en = 'Video: Integration — the core idea' WHERE resource_id = 13;
UPDATE resources SET resource_title_en = 'Podcast: Calculus Stories (ep. 2)' WHERE resource_id = 14;
UPDATE resources SET resource_title_en = 'Quiz: Calculus 2' WHERE resource_id = 15;
UPDATE resources SET resource_title_en = 'Practical activity: model an optimization problem' WHERE resource_id = 16;
UPDATE resources SET resource_title_en = 'Reinforcement: Quantum Computing principles in 10 min' WHERE resource_id = 17;
UPDATE resources SET resource_title_en = 'Reinforcement (text): What is quantum computing?' WHERE resource_id = 18;
UPDATE resources SET resource_title_en = 'Reinforcement: Real applications of Quantum Computing' WHERE resource_id = 19;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Quantum computing use cases' WHERE resource_id = 20;
UPDATE resources SET resource_title_en = 'Reinforcement: Why building a quantum computer is hard' WHERE resource_id = 21;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Decoherence and error correction' WHERE resource_id = 22;
UPDATE resources SET resource_title_en = 'Reinforcement: Derivatives from scratch (3Blue1Brown)' WHERE resource_id = 23;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Differentiation rules' WHERE resource_id = 24;
UPDATE resources SET resource_title_en = 'Reinforcement: Understanding limits intuitively' WHERE resource_id = 25;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Limits and continuity' WHERE resource_id = 26;
UPDATE resources SET resource_title_en = 'Reinforcement: Maxima and minima with derivatives' WHERE resource_id = 27;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Optimization and critical points' WHERE resource_id = 28;
UPDATE resources SET resource_title_en = 'Reading: What is Cloud Computing' WHERE resource_id = 29;
UPDATE resources SET resource_title_en = 'Video: Cloud computing explained' WHERE resource_id = 30;
UPDATE resources SET resource_title_en = 'Podcast: Cloud in practice (ep. 1)' WHERE resource_id = 31;
UPDATE resources SET resource_title_en = 'Quiz: Cloud Computing' WHERE resource_id = 32;
UPDATE resources SET resource_title_en = 'Practical activity: spin up a free VM on AWS/Azure' WHERE resource_id = 33;
UPDATE resources SET resource_title_en = 'Reinforcement: IaaS, PaaS and SaaS in 5 minutes' WHERE resource_id = 34;
UPDATE resources SET resource_title_en = 'Reinforcement (text): What is cloud computing (AWS)' WHERE resource_id = 35;
UPDATE resources SET resource_title_en = 'Reinforcement: Public, private and hybrid cloud' WHERE resource_id = 36;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Microsoft Azure (portal)' WHERE resource_id = 37;
UPDATE resources SET resource_title_en = 'Reinforcement: Security and shared responsibility' WHERE resource_id = 38;
UPDATE resources SET resource_title_en = 'Reinforcement (text): Dictionary — what is cloud computing (Azure)' WHERE resource_id = 39;

-- ---------------------------------------------------------------------------
-- 5. Questões (enunciado + alternativas, na MESMA ordem do PT — o gabarito por
--    letra continua válido)
-- ---------------------------------------------------------------------------
UPDATE questions SET
  statement_en = 'Which of the following statements best describes quantum superposition?',
  alternatives_en = '{"alternatives": ["A qubit can be in a state of 0 or 1.", "A qubit can be in a state of 0, 1, or both at the same time.", "A qubit can only be 0 or 1 after measurement.", "A qubit cannot change its state once set."]}'
WHERE question_id = 1;

UPDATE questions SET
  statement_en = 'What is quantum entanglement?',
  alternatives_en = '{"alternatives": ["The ability of a qubit to be 0 and 1 simultaneously.", "The instantaneous connection between two qubits separated by great distances.", "The property of a qubit changing state when measured.", "The impossibility of measuring the state of a qubit."]}'
WHERE question_id = 2;

UPDATE questions SET
  statement_en = 'How do qubits differ from traditional bits?',
  alternatives_en = '{"alternatives": ["Qubits can store more than two states.", "Qubits can only be in state 0 or 1.", "Qubits are only used in personal computers.", "Qubits are not affected by the environment."]}'
WHERE question_id = 3;

UPDATE questions SET
  statement_en = 'Which of the following areas is most impacted by quantum computing?',
  alternatives_en = '{"alternatives": ["Medicine", "Finance", "Cybersecurity", "All of the above"]}'
WHERE question_id = 4;

UPDATE questions SET
  statement_en = 'How can quantum computing improve cryptography?',
  alternatives_en = '{"alternatives": ["By using algorithms that cannot be broken by classical computers.", "By increasing the speed of brute-force calculations.", "By making data invisible to hackers.", "By allowing data transmission without the need for keys."]}'
WHERE question_id = 5;

UPDATE questions SET
  statement_en = 'In which of the following applications is quantum simulation most relevant?',
  alternatives_en = '{"alternatives": ["Development of new medicines", "Creating graphics for games", "Social networks", "Video editing"]}'
WHERE question_id = 6;

UPDATE questions SET
  statement_en = 'Which of the following is NOT a challenge of quantum computing?',
  alternatives_en = '{"alternatives": ["Quantum errors", "Refrigeration", "Decoherence", "Lack of skilled workforce"]}'
WHERE question_id = 7;

UPDATE questions SET
  statement_en = 'What is decoherence in quantum computing?',
  alternatives_en = '{"alternatives": ["The ability of a qubit to keep its superposition indefinitely.", "The loss of quantum information due to interaction with the environment.", "The need to refrigerate qubits at high temperatures.", "The instantaneous measurement of two entangled qubits."]}'
WHERE question_id = 8;

UPDATE questions SET
  statement_en = 'Why is refrigeration a challenge in quantum computing?',
  alternatives_en = '{"alternatives": ["Because qubits need to be constantly heated.", "Because qubits work best at room temperature.", "Because qubits must be kept at temperatures near absolute zero.", "Because refrigeration does not affect the state of qubits."]}'
WHERE question_id = 9;

UPDATE questions SET
  statement_en = 'Compute the derivative of the function f(x)=3x²+2x+1.',
  alternatives_en = '{"alternatives": ["3x²+2", "6x+2", "6x²+2", "6x+1"]}'
WHERE question_id = 10;

UPDATE questions SET
  statement_en = 'What is the derivative of the function g(x)=e^x?',
  alternatives_en = '{"alternatives": ["e^x", "x.e^x", "e^(x-1)", "x.e^(x-1)"]}'
WHERE question_id = 11;

UPDATE questions SET
  statement_en = 'Compute the indefinite integral of f(x)=4x³',
  alternatives_en = '{"alternatives": ["x⁴+C", "x⁴", "(x⁴/4)+C", "(x⁴/2)+C"]}'
WHERE question_id = 12;

UPDATE questions SET
  statement_en = 'Compute the limit lim(x->2)(3x-4)',
  alternatives_en = '{"alternatives": ["6", "4", "2", "8"]}'
WHERE question_id = 13;

UPDATE questions SET
  statement_en = 'What is the limit lim(x->infinity)(1/x)?',
  alternatives_en = '{"alternatives": ["1", "0", "Infinity", "-1"]}'
WHERE question_id = 14;

UPDATE questions SET
  statement_en = 'Compute the limit of the function (3x²-2x+1)/(x-1) as x approaches 1',
  alternatives_en = '{"alternatives": ["Infinity", "1", "4", "2", "Does not exist"]}'
WHERE question_id = 15;

UPDATE questions SET
  statement_en = 'The function f(x)=x² has a minimum point at:',
  alternatives_en = '{"alternatives": ["x=0", "x=1", "x=-1", "x=2"]}'
WHERE question_id = 16;

UPDATE questions SET
  statement_en = 'For the function h(x)=-2x²+4x, the maximum point is:',
  alternatives_en = '{"alternatives": ["x=0", "x=-1", "x=2", "x=1"]}'
WHERE question_id = 17;

UPDATE questions SET
  statement_en = 'Consider the function f(x)=-2x²+4x+1. Determine whether the critical point of the function is a maximum or a minimum.',
  alternatives_en = '{"alternatives": ["Maximum point", "Minimum point", "There is no critical point", "None of the above"]}'
WHERE question_id = 18;

UPDATE questions SET
  statement_en = 'What is the derivative of the function f(x) = sin(x)?',
  alternatives_en = '{"alternatives": ["cos(x)", "-cos(x)", "sin(x)", "-sin(x)"]}'
WHERE question_id = 19;

UPDATE questions SET
  statement_en = 'Compute the indefinite integral of the function f(x) = cos(x).',
  alternatives_en = '{"alternatives": ["sin(x) + C", "-sin(x) + C", "x.cos(x)", "-x.sin(x)"]}'
WHERE question_id = 20;

UPDATE questions SET
  statement_en = 'What is the value of the limit lim(x->0)(sin(x)/x)?',
  alternatives_en = '{"alternatives": ["0", "1", "Infinity", "-1"]}'
WHERE question_id = 21;

UPDATE questions SET
  statement_en = 'Determine the limit lim(x->1)(x^2 - 1)/(x - 1).',
  alternatives_en = '{"alternatives": ["0", "1", "2", "Does not exist"]}'
WHERE question_id = 22;

UPDATE questions SET
  statement_en = 'Compute the limit lim(x->0)(e^x - 1)/x.',
  alternatives_en = '{"alternatives": ["1", "0", "Infinity", "-1"]}'
WHERE question_id = 23;

UPDATE questions SET
  statement_en = 'For the function f(x) = x^2 - 4x + 3, the minimum point occurs at:',
  alternatives_en = '{"alternatives": ["x=1", "x=2", "x=3", "x=4"]}'
WHERE question_id = 24;

UPDATE questions SET
  statement_en = 'At which point x does the function f(x) = -x^2 + 6x - 9 have a maximum?',
  alternatives_en = '{"alternatives": ["x=1", "x=2", "x=3", "x=4"]}'
WHERE question_id = 25;

UPDATE questions SET
  statement_en = 'For the function f(x) = x^3 - 3x^2 + 2, determine whether x=2 is a maximum or a minimum point.',
  alternatives_en = '{"alternatives": ["Maximum point", "Minimum point", "None of the above", "It is not a critical point"]}'
WHERE question_id = 26;

UPDATE questions SET
  statement_en = 'Which service model delivers virtual machines, networking and storage, leaving the operating system and applications under the customer''s responsibility?',
  alternatives_en = '{"alternatives": ["SaaS", "PaaS", "IaaS", "On-premise"]}'
WHERE question_id = 27;

UPDATE questions SET
  statement_en = 'In the SaaS model, what does the customer typically manage?',
  alternatives_en = '{"alternatives": ["The physical infrastructure", "The servers'' operating system", "Only the use of the application", "The runtime environment"]}'
WHERE question_id = 28;

UPDATE questions SET
  statement_en = 'What is the deployment model that combines public and private cloud called?',
  alternatives_en = '{"alternatives": ["Community cloud", "Hybrid cloud", "Dedicated cloud", "Multi-tenant"]}'
WHERE question_id = 29;

UPDATE questions SET
  statement_en = 'An advantage of the public cloud over the private cloud is:',
  alternatives_en = '{"alternatives": ["Greater control over the hardware", "Lower upfront cost and greater elasticity", "Guaranteed physical isolation", "No need for the internet"]}'
WHERE question_id = 30;

UPDATE questions SET
  statement_en = 'Which economic model characterizes cloud computing?',
  alternatives_en = '{"alternatives": ["Perpetual license", "Pay-as-you-go", "Purchasing physical servers", "Mandatory lifetime subscription"]}'
WHERE question_id = 31;

UPDATE questions SET
  statement_en = 'In the shared responsibility model, who configures access and encrypts the data?',
  alternatives_en = '{"alternatives": ["Only the cloud provider", "The customer", "The internet provider", "No one"]}'
WHERE question_id = 32;
