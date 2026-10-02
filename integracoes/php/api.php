<?php
/**
 * API PHP autônoma do EduBot (Caminho B) — lê o MySQL direto, via PDO.
 *
 * Quando usar: a hospedagem disponível é PHP/cPanel e subir o Flask não é uma
 * opção, ou você quer um endpoint isolado do backend principal.
 *
 * Quando NÃO usar: se o Flask já está no ar, prefira `/api/v1` — as chaves ficam
 * em banco (revogáveis sem editar arquivo), as regras de escopo são testadas
 * (tests/test_public_api.py) e existe um único lugar onde a política de acesso
 * mora. Este arquivo é uma segunda porta, e toda segunda porta precisa ser
 * trancada de novo: se você adicionar um endpoint no Flask, ele NÃO aparece aqui.
 *
 * Contrato idêntico ao do Flask — de propósito, para que o mesmo
 * `edubot_client.php` sirva aos dois:
 *
 *     GET api.php?recurso=ovas
 *     GET api.php?recurso=eventos&after_id=0&limit=100
 *     Header: X-API-Key: ek_php_...
 *
 * Instalação em 4 passos — veja INTEGRACAO_API_EXTERNA.md.
 */

declare(strict_types=1);

require_once __DIR__ . '/config.php';

header('Content-Type: application/json; charset=utf-8');
// Respostas de API não devem ser cacheadas por proxy: elas variam por chave.
header('Cache-Control: no-store');
// O navegador não deve adivinhar o tipo do conteúdo (evita XSS por sniffing
// caso algum dado do banco contenha HTML).
header('X-Content-Type-Options: nosniff');

// ---------------------------------------------------------------------------
// Saída
// ---------------------------------------------------------------------------

function responder(array $payload, int $status = 200): void
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function erro(string $mensagem, int $status): void
{
    responder(['error' => $mensagem, 'status' => $status], $status);
}

// ---------------------------------------------------------------------------
// Autenticação por chave + escopo
// ---------------------------------------------------------------------------

/** Lê a chave do header. Nem todo servidor entrega HTTP_X_API_KEY (alguns
 *  FastCGI filtram headers não-padrão), então há dois caminhos de leitura. */
function chave_recebida(): string
{
    if (!empty($_SERVER['HTTP_X_API_KEY'])) {
        return trim((string) $_SERVER['HTTP_X_API_KEY']);
    }
    if (function_exists('getallheaders')) {
        foreach (getallheaders() as $nome => $valor) {
            if (strcasecmp($nome, 'X-API-Key') === 0) {
                return trim((string) $valor);
            }
            if (strcasecmp($nome, 'Authorization') === 0 && stripos((string) $valor, 'apikey ') === 0) {
                return trim(substr((string) $valor, 7));
            }
        }
    }
    return '';
}

/** Escopos da chave apresentada, ou null se a chave não for conhecida. */
function escopos_da_chave(string $chave): ?array
{
    if ($chave === '') {
        return null;
    }
    // hash_equals a cada candidata, em vez de isset($mapa[$chave]): a busca por
    // índice compara byte a byte e para no primeiro que difere, o que deixa o
    // tempo de resposta vazar informação sobre o prefixo da chave correta.
    foreach (EDUBOT_PHP_KEYS as $valida => $escopos) {
        if (hash_equals((string) $valida, $chave)) {
            return array_values(array_filter(array_map('trim', explode(',', (string) $escopos))));
        }
    }
    return null;
}

$chave = chave_recebida();
$escopos = escopos_da_chave($chave);
if ($escopos === null) {
    erro('Chave de API ausente ou inválida.', 401);
}

function exigir_escopo(string $escopo): void
{
    global $escopos;
    if (!in_array($escopo, $escopos, true)) {
        erro("Chave sem permissão. Escopo necessário: {$escopo}.", 403);
    }
}

function tem_escopo(string $escopo): bool
{
    global $escopos;
    return in_array($escopo, $escopos, true);
}

// ---------------------------------------------------------------------------
// Banco
// ---------------------------------------------------------------------------

function pdo(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $dsn = sprintf('mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4',
                       EDUBOT_DB_HOST, EDUBOT_DB_PORT, EDUBOT_DB_NAME);
        try {
            $pdo = new PDO($dsn, EDUBOT_DB_USER, EDUBOT_DB_PASS, [
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                // false = prepared statement REAL no servidor MySQL. Com a
                // emulação ligada (padrão do PDO), o driver interpola os
                // parâmetros na string SQL do lado do PHP — o que reabre a porta
                // para injeção em casos de borda de charset. Aqui não.
                PDO::ATTR_EMULATE_PREPARES   => false,
            ]);
        } catch (PDOException $e) {
            // A mensagem do PDO traz host, usuário e às vezes a senha. Ela vai
            // para o log do servidor, nunca para a resposta HTTP.
            error_log('EduBot API — falha de conexão: ' . $e->getMessage());
            erro('Falha ao conectar no banco de dados.', 500);
        }
    }
    return $pdo;
}

function consultar(string $sql, array $params = []): array
{
    try {
        $stmt = pdo()->prepare($sql);
        $stmt->execute($params);
        return $stmt->fetchAll();
    } catch (PDOException $e) {
        error_log('EduBot API — falha de consulta: ' . $e->getMessage());
        erro('Falha ao consultar o banco de dados.', 500);
    }
    return [];
}

// ---------------------------------------------------------------------------
// Parâmetros
// ---------------------------------------------------------------------------

const LIMITE_MAXIMO = 500;

function limite(): int
{
    $bruto = isset($_GET['limit']) ? (int) $_GET['limit'] : 100;
    return max(1, min($bruto, LIMITE_MAXIMO));
}

function inteiro(string $nome): ?int
{
    return isset($_GET[$nome]) && $_GET[$nome] !== '' ? (int) $_GET[$nome] : null;
}

/** Data ISO da query string, validada. Retorna null se ausente; encerra com 400
 *  se presente e malformada (filtro que não filtra é pior que filtro ausente). */
function data(string $nome): ?string
{
    if (empty($_GET[$nome])) {
        return null;
    }
    $bruto = (string) $_GET[$nome];
    foreach (['Y-m-d H:i:s', 'Y-m-d\TH:i:s', 'Y-m-d'] as $formato) {
        $dt = DateTime::createFromFormat($formato, $bruto);
        if ($dt !== false) {
            return $dt->format('Y-m-d H:i:s');
        }
    }
    erro("Parâmetro `{$nome}` inválido: use ISO-8601 (2026-09-01 ou 2026-09-01T14:30:00).", 400);
    return null;
}

/**
 * Pseudônimo do aluno — MESMO algoritmo do Flask (api/apikey.py::pseudonym):
 * sha256("<salt>:<student_id>") truncado em 16 hex. Precisa bater byte a byte,
 * senão os dois caminhos geram identificadores diferentes para o mesmo aluno e
 * o parceiro não consegue cruzar os dados.
 */
function pseudonimo(int $studentId): string
{
    return substr(hash('sha256', EDUBOT_PSEUDONYM_SALT . ':' . $studentId), 0, 16);
}

/** Troca student_id por subject_id nas linhas. Com `students:pii`, mantém os dois. */
function pseudonimizar(array $linhas): array
{
    $pii = tem_escopo('students:pii');
    foreach ($linhas as &$linha) {
        if (!isset($linha['student_id'])) {
            continue;
        }
        $id = (int) $linha['student_id'];
        if (!$pii) {
            unset($linha['student_id']);
        }
        // subject_id primeiro na ordem das chaves, como no Flask.
        $linha = array_merge(['subject_id' => pseudonimo($id)], $linha);
    }
    unset($linha);   // solta a referência do foreach (footgun clássico do PHP)
    return $linhas;
}

/** Envelope de paginação por cursor — igual ao do Flask. */
function pagina(array $linhas, string $campoId, int $limite): array
{
    $ultimo = $linhas ? end($linhas) : null;
    reset($linhas);
    return [
        'data'          => $linhas,
        'count'         => count($linhas),
        'next_after_id' => (count($linhas) === $limite && $ultimo !== null)
                           ? (int) $ultimo[$campoId] : null,
    ];
}

// ---------------------------------------------------------------------------
// Roteamento
//
// `$recurso` NUNCA entra numa string SQL: ele só escolhe qual bloco roda, e cada
// bloco tem seu SQL fixo com placeholders. É por isso que um `?recurso=` hostil
// não tem por onde virar injeção.
// ---------------------------------------------------------------------------

$recurso = isset($_GET['recurso']) ? (string) $_GET['recurso'] : 'ping';

switch ($recurso) {

    case 'ping':
        responder([
            'ok'          => true,
            'service'     => 'EduBot PHP API',
            'version'     => 'v1',
            'server_time' => date('c'),
            'scopes'      => $escopos,
        ]);
        // no break — responder() encerra

    case 'cursos':
        exigir_escopo('catalog:read');
        $linhas = consultar('SELECT course_id, course_name FROM courses ORDER BY course_id');
        responder(['data' => $linhas, 'count' => count($linhas)]);

    case 'ovas':
        exigir_escopo('catalog:read');
        $sql = 'SELECT o.ova_id, o.ova_name, o.subject_id, o.num_interactions,
                       o.link, o.quiz_gate_perc, s.subject_name
                  FROM ovas o
                  LEFT JOIN course_subjects s ON s.subject_id = o.subject_id';
        $params = [];
        if (($subjectId = inteiro('subject_id')) !== null) {
            $sql .= ' WHERE o.subject_id = :subject_id';
            $params['subject_id'] = $subjectId;
        }
        $linhas = consultar($sql . ' ORDER BY o.ova_id', $params);
        responder(['data' => $linhas, 'count' => count($linhas)]);

    case 'competencias':
        exigir_escopo('catalog:read');
        $linhas = consultar(
            'SELECT c.competency_id, c.competency_description, c.subject_id, s.subject_name
               FROM competencies c
               LEFT JOIN course_subjects s ON s.subject_id = c.subject_id
              ORDER BY c.competency_id');
        responder(['data' => $linhas, 'count' => count($linhas)]);

    case 'questoes':
        exigir_escopo('catalog:read');
        $incluirGabarito = isset($_GET['include_answer']) &&
                           in_array(strtolower((string) $_GET['include_answer']),
                                    ['1', 'true', 'yes'], true);
        // A coluna do gabarito entra por uma constante escolhida pelo if, não
        // por texto vindo do usuário.
        $colunas = 'question_id, statement, alternatives, ova_id, competency_id, difficulty'
                 . ($incluirGabarito ? ', answer' : '');
        $sql = "SELECT {$colunas} FROM questions";
        $where = [];
        $params = [];
        if (($ovaId = inteiro('ova_id')) !== null) {
            $where[] = 'ova_id = :ova_id';
            $params['ova_id'] = $ovaId;
        }
        if (($compId = inteiro('competency_id')) !== null) {
            $where[] = 'competency_id = :competency_id';
            $params['competency_id'] = $compId;
        }
        if ($where) {
            $sql .= ' WHERE ' . implode(' AND ', $where);
        }
        $linhas = consultar($sql . ' ORDER BY question_id', $params);
        // `alternatives` é JSON no MySQL e chega como string; devolver decodificado
        // poupa o parceiro de um json_decode aninhado.
        foreach ($linhas as &$q) {
            if (isset($q['alternatives']) && is_string($q['alternatives'])) {
                $q['alternatives'] = json_decode($q['alternatives'], true);
            }
        }
        unset($q);
        responder(['data' => $linhas, 'count' => count($linhas),
                   'gabarito_incluido' => $incluirGabarito]);

    case 'eventos':
        exigir_escopo('tracking:read');
        $limite = limite();
        $sql = 'SELECT event_id, student_id, verb, object_type, object_id, context, occurred_at
                  FROM learning_events WHERE 1=1';
        $params = [];
        if (($afterId = inteiro('after_id')) !== null) {
            $sql .= ' AND event_id > :after_id';
            $params['after_id'] = $afterId;
        }
        if (($desde = data('since')) !== null) {
            $sql .= ' AND occurred_at >= :since';
            $params['since'] = $desde;
        }
        if (($ate = data('until')) !== null) {
            $sql .= ' AND occurred_at <= :until';
            $params['until'] = $ate;
        }
        if (!empty($_GET['verb'])) {
            $sql .= ' AND verb = :verb';
            $params['verb'] = (string) $_GET['verb'];
        }
        // LIMIT não aceita placeholder em prepared statement real, por isso o
        // valor é interpolado — mas já passou por limite(), que o força a ser um
        // int entre 1 e 500. Não há caminho para texto do usuário chegar aqui.
        $linhas = consultar($sql . " ORDER BY event_id ASC LIMIT {$limite}", $params);

        $pii = tem_escopo('students:pii');
        foreach ($linhas as &$ev) {
            if (isset($ev['context']) && is_string($ev['context'])) {
                $ev['context'] = json_decode($ev['context'], true);
            }
            // Mesma barreira do Flask: texto livre escrito pelo aluno só com PII.
            if (!$pii && is_array($ev['context'])) {
                foreach (['text', 'question', 'prompt'] as $chaveTexto) {
                    if (array_key_exists($chaveTexto, $ev['context'])) {
                        $ev['context'][$chaveTexto] = null;
                    }
                }
            }
        }
        unset($ev);
        responder(pagina(pseudonimizar($linhas), 'event_id', $limite));

    case 'progresso':
        exigir_escopo('tracking:read');
        $limite = limite();
        $sql = 'SELECT progress_id, student_id, ova_id, read_time AS read_time_seconds,
                       perc_scrolled, completed, last_access
                  FROM ova_progress WHERE 1=1';
        $params = [];
        if (($afterId = inteiro('after_id')) !== null) {
            $sql .= ' AND progress_id > :after_id';
            $params['after_id'] = $afterId;
        }
        if (($ovaId = inteiro('ova_id')) !== null) {
            $sql .= ' AND ova_id = :ova_id';
            $params['ova_id'] = $ovaId;
        }
        $linhas = consultar($sql . " ORDER BY progress_id ASC LIMIT {$limite}", $params);
        foreach ($linhas as &$p) {
            $p['completed'] = (bool) $p['completed'];
        }
        unset($p);
        responder(pagina(pseudonimizar($linhas), 'progress_id', $limite));

    case 'secoes':
        exigir_escopo('tracking:read');
        $limite = limite();
        $sql = 'SELECT section_progress_id, student_id, ova_id, section_id, section_index,
                       active_seconds, max_scroll_perc, visits, last_access
                  FROM ova_section_progress WHERE 1=1';
        $params = [];
        if (($afterId = inteiro('after_id')) !== null) {
            $sql .= ' AND section_progress_id > :after_id';
            $params['after_id'] = $afterId;
        }
        if (($ovaId = inteiro('ova_id')) !== null) {
            $sql .= ' AND ova_id = :ova_id';
            $params['ova_id'] = $ovaId;
        }
        $linhas = consultar($sql . " ORDER BY section_progress_id ASC LIMIT {$limite}", $params);
        responder(pagina(pseudonimizar($linhas), 'section_progress_id', $limite));

    case 'dominio':
        exigir_escopo('metrics:read');
        $linhas = consultar(
            'SELECT m.competency_id, c.competency_description AS competencia,
                    ROUND(AVG(m.p_mastery), 4) AS dominio_medio,
                    COUNT(m.student_id)        AS alunos,
                    SUM(m.attempts_seen)       AS tentativas
               FROM student_mastery m
               LEFT JOIN competencies c ON c.competency_id = m.competency_id
              GROUP BY m.competency_id, c.competency_description
              ORDER BY dominio_medio ASC');
        foreach ($linhas as &$linha) {
            $linha['dominio_medio'] = (float) $linha['dominio_medio'];
            $linha['alunos']        = (int) $linha['alunos'];
            $linha['tentativas']    = (int) $linha['tentativas'];
        }
        unset($linha);
        responder(['data' => $linhas, 'count' => count($linhas)]);

    case 'questoes_desempenho':
        exigir_escopo('metrics:read');
        $linhas = consultar(
            'SELECT question_id,
                    COUNT(attempt_id) AS tentativas,
                    SUM(is_correct)   AS acertos,
                    ROUND(SUM(is_correct) / COUNT(attempt_id), 4) AS taxa_acerto
               FROM attempts
              GROUP BY question_id
              ORDER BY taxa_acerto ASC');
        foreach ($linhas as &$linha) {
            $linha['tentativas'] = (int) $linha['tentativas'];
            $linha['acertos']    = (int) $linha['acertos'];
            $linha['taxa_acerto'] = $linha['taxa_acerto'] === null
                ? null : (float) $linha['taxa_acerto'];
        }
        unset($linha);
        responder(['data' => $linhas, 'count' => count($linhas)]);

    case 'engajamento':
        exigir_escopo('metrics:read');
        $sql = 'SELECT verb, COUNT(event_id) AS eventos, COUNT(DISTINCT student_id) AS alunos
                  FROM learning_events WHERE 1=1';
        $params = [];
        if (($desde = data('since')) !== null) {
            $sql .= ' AND occurred_at >= :since';
            $params['since'] = $desde;
        }
        if (($ate = data('until')) !== null) {
            $sql .= ' AND occurred_at <= :until';
            $params['until'] = $ate;
        }
        $linhas = consultar($sql . ' GROUP BY verb ORDER BY eventos DESC', $params);
        foreach ($linhas as &$linha) {
            $linha['eventos'] = (int) $linha['eventos'];
            $linha['alunos']  = (int) $linha['alunos'];
        }
        unset($linha);
        responder(['data' => $linhas, 'count' => count($linhas)]);

    case 'alunos':
        exigir_escopo('students:read');
        $pii = tem_escopo('students:pii');
        // Sem PII as colunas nem são SELECIONADAS — não basta omitir na saída:
        // se o dado não é lido, não há como vazar por log, erro ou var_dump.
        // (E com o GRANT por coluna do usuario_somente_leitura.sql, o banco
        //  recusaria a leitura de qualquer forma.)
        $colunas = 'student_id, course_id, role, is_admin, persona, nickname'
                 . ($pii ? ', student_name, ra' : '');
        $sql = "SELECT {$colunas} FROM students";
        $params = [];
        if (($cursoId = inteiro('course_id')) !== null) {
            $sql .= ' WHERE course_id = :course_id';
            $params['course_id'] = $cursoId;
        }
        $limite = limite();
        $linhas = consultar($sql . " ORDER BY student_id LIMIT {$limite}", $params);
        foreach ($linhas as &$a) {
            $a['is_admin'] = (bool) $a['is_admin'];
        }
        unset($a);
        responder(['data' => pseudonimizar($linhas), 'count' => count($linhas),
                   'pii_incluido' => $pii]);

    default:
        erro("Recurso `{$recurso}` não existe. Disponíveis: ping, cursos, ovas, "
           . "competencias, questoes, eventos, progresso, secoes, dominio, "
           . "questoes_desempenho, engajamento, alunos.", 404);
}
