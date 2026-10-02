<?php
/**
 * Cliente PHP da API pública do EduBot (Caminho A).
 *
 * É este arquivo que a pessoa externa cola no app dela. Ele fala HTTP com o
 * Flask (`/api/v1/...`) e não conhece o MySQL — que é justamente o ponto: o
 * parceiro nunca recebe credencial de banco, e o que ele pode ler é decidido
 * pelos escopos da chave, do lado do servidor.
 *
 * Requisitos: PHP 7.4+ com a extensão cURL (`php-curl`). Sem cURL, cai
 * automaticamente para `file_get_contents` com stream context — hospedagens
 * compartilhadas antigas costumam ter só isso.
 *
 * Uso:
 *
 *     require __DIR__ . '/edubot_client.php';
 *     $edubot = new EduBotClient(EDUBOT_API_BASE, EDUBOT_API_KEY);
 *
 *     $ovas = $edubot->ovas();
 *     foreach ($edubot->eventosDesde(0) as $ev) { ... }
 */

require_once __DIR__ . '/config.php';

/** Erro de chamada à API — mensagem já tratada e status HTTP preservado. */
class EduBotApiException extends RuntimeException
{
    public int $statusHttp;
    public function __construct(string $mensagem, int $statusHttp = 0)
    {
        parent::__construct($mensagem);
        $this->statusHttp = $statusHttp;
    }
}

class EduBotClient
{
    private string $base;
    private string $chave;
    private int $timeout;
    private bool $verificarTls;

    public function __construct(
        string $base = EDUBOT_API_BASE,
        string $chave = EDUBOT_API_KEY,
        int $timeout = EDUBOT_TIMEOUT,
        bool $verificarTls = EDUBOT_VERIFY_TLS
    ) {
        $this->base = rtrim($base, '/');
        $this->chave = $chave;
        $this->timeout = $timeout;
        $this->verificarTls = $verificarTls;
    }

    // -----------------------------------------------------------------------
    // Transporte
    // -----------------------------------------------------------------------

    /**
     * GET em `/api/v1/$caminho` com os parâmetros dados. Retorna o corpo já
     * decodificado como array associativo.
     *
     * Os valores de `$params` passam por http_build_query, que os escapa — por
     * isso não há concatenação manual de query string em lugar nenhum daqui.
     */
    public function get(string $caminho, array $params = []): array
    {
        $url = $this->base . '/api/v1/' . ltrim($caminho, '/');
        if ($params) {
            $url .= '?' . http_build_query($params);
        }
        [$corpo, $status] = function_exists('curl_init')
            ? $this->viaCurl($url)
            : $this->viaStream($url);

        if ($corpo === null) {
            throw new EduBotApiException("Falha de rede ao chamar {$url}", 0);
        }

        $dados = json_decode($corpo, true);
        if ($status >= 400) {
            // O servidor manda {"error": "...", "status": n} em toda falha.
            $msg = is_array($dados) && isset($dados['error'])
                ? $dados['error']
                : "HTTP {$status}";
            throw new EduBotApiException($this->explicar($status, $msg), $status);
        }
        if (!is_array($dados)) {
            throw new EduBotApiException("Resposta não é JSON válido: " . substr($corpo, 0, 200), $status);
        }
        return $dados;
    }

    /** Traduz os status que mais aparecem para algo acionável por quem integra. */
    private function explicar(int $status, string $msg): string
    {
        switch ($status) {
            case 401:
                return "401 — chave inválida, revogada ou expirada. Confira EDUBOT_API_KEY. ({$msg})";
            case 403:
                return "403 — a chave é válida mas não tem o escopo necessário. "
                     . "Chame /scopes para ver o que ela tem e peça o escopo que falta. ({$msg})";
            case 429:
                return "429 — limite de requisições excedido. Espere a janela virar "
                     . "ou aumente o limit por página para fazer menos chamadas. ({$msg})";
            default:
                return "HTTP {$status} — {$msg}";
        }
    }

    /** @return array{0: ?string, 1: int} */
    private function viaCurl(string $url): array
    {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => $this->timeout,
            CURLOPT_HTTPHEADER     => [
                'X-API-Key: ' . $this->chave,
                'Accept: application/json',
            ],
            CURLOPT_SSL_VERIFYPEER => $this->verificarTls,
            CURLOPT_SSL_VERIFYHOST => $this->verificarTls ? 2 : 0,
            CURLOPT_FOLLOWLOCATION => false,  // um redirect levaria a chave junto
        ]);
        $corpo = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $erro = curl_error($ch);
        curl_close($ch);
        if ($corpo === false) {
            throw new EduBotApiException("cURL: {$erro}", 0);
        }
        return [$corpo, $status];
    }

    /** @return array{0: ?string, 1: int} */
    private function viaStream(string $url): array
    {
        $ctx = stream_context_create([
            'http' => [
                'method'        => 'GET',
                'header'        => "X-API-Key: {$this->chave}\r\nAccept: application/json\r\n",
                'timeout'       => $this->timeout,
                // Sem isto, um 4xx faz file_get_contents devolver false e a
                // mensagem de erro do servidor se perde.
                'ignore_errors' => true,
                'follow_location' => 0,
            ],
            'ssl' => [
                'verify_peer'      => $this->verificarTls,
                'verify_peer_name' => $this->verificarTls,
            ],
        ]);
        $corpo = @file_get_contents($url, false, $ctx);
        $status = 0;
        // $http_response_header é populada pelo wrapper HTTP no escopo local.
        if (isset($http_response_header[0]) &&
            preg_match('#HTTP/\S+\s+(\d{3})#', $http_response_header[0], $m)) {
            $status = (int) $m[1];
        }
        return [$corpo === false ? null : $corpo, $status];
    }

    // -----------------------------------------------------------------------
    // Diagnóstico
    // -----------------------------------------------------------------------

    /** Confere chave e conectividade. É a primeira chamada a fazer. */
    public function ping(): array
    {
        return $this->get('ping');
    }

    /** Escopos existentes e quais esta chave tem. Resolve 403 sem abrir chamado. */
    public function escopos(): array
    {
        return $this->get('scopes')['scopes'];
    }

    // -----------------------------------------------------------------------
    // Catálogo (escopo catalog:read)
    // -----------------------------------------------------------------------

    public function cursos(): array
    {
        return $this->get('catalog/courses')['data'];
    }

    public function ovas(?int $subjectId = null): array
    {
        return $this->get('catalog/ovas', $subjectId ? ['subject_id' => $subjectId] : [])['data'];
    }

    public function competencias(): array
    {
        return $this->get('catalog/competencies')['data'];
    }

    /**
     * Questões. `$incluirGabarito` só quando o PHP for corrigir no servidor —
     * se a resposta chegar ao navegador do aluno, o gabarito vai junto.
     */
    public function questoes(?int $ovaId = null, bool $incluirGabarito = false): array
    {
        $params = [];
        if ($ovaId !== null)   { $params['ova_id'] = $ovaId; }
        if ($incluirGabarito)  { $params['include_answer'] = 1; }
        return $this->get('catalog/questions', $params)['data'];
    }

    // -----------------------------------------------------------------------
    // Rastreio (escopo tracking:read)
    // -----------------------------------------------------------------------

    /** Uma página de eventos. Use `eventosDesde()` para varrer tudo. */
    public function eventos(array $filtros = []): array
    {
        return $this->get('tracking/events', $filtros);
    }

    /**
     * Varre TODOS os eventos a partir de um cursor, página por página.
     *
     * É um Generator: o app do parceiro processa evento a evento sem carregar a
     * base inteira em memória. O padrão de sincronização é guardar o último
     * `event_id` processado e passá-lo como `$aPartirDe` na próxima rodada —
     * cada evento chega exatamente uma vez.
     *
     *     $ultimo = (int) file_get_contents('cursor.txt');
     *     foreach ($edubot->eventosDesde($ultimo) as $ev) {
     *         processar($ev);
     *         $ultimo = $ev['event_id'];
     *     }
     *     file_put_contents('cursor.txt', $ultimo);
     */
    public function eventosDesde(int $aPartirDe = 0, array $filtros = [], int $porPagina = 500): Generator
    {
        $cursor = $aPartirDe;
        while (true) {
            // array_merge e NÃO `$filtros + [...]`: na união com `+` o operando
            // da esquerda vence, então um `after_id` deixado em $filtros
            // sobrescreveria o cursor e a varredura repetiria a mesma página
            // para sempre. Aqui o cursor sempre ganha.
            $pagina = $this->eventos(array_merge($filtros, [
                'after_id' => $cursor,
                'limit'    => $porPagina,
            ]));
            foreach ($pagina['data'] as $evento) {
                yield $evento;
            }
            if ($pagina['next_after_id'] === null) {
                return;
            }
            $cursor = $pagina['next_after_id'];
        }
    }

    public function progresso(array $filtros = []): array
    {
        return $this->get('tracking/progress', $filtros);
    }

    public function secoes(array $filtros = []): array
    {
        return $this->get('tracking/sections', $filtros);
    }

    // -----------------------------------------------------------------------
    // Métricas (escopo metrics:read)
    // -----------------------------------------------------------------------

    public function dominioPorCompetencia(): array
    {
        return $this->get('metrics/mastery')['data'];
    }

    public function desempenhoPorQuestao(): array
    {
        return $this->get('metrics/questions')['data'];
    }

    public function cobertura(?int $cursoId = null): array
    {
        return $this->get('metrics/coverage', $cursoId ? ['course_id' => $cursoId] : [])['data'];
    }

    public function engajamento(?string $desde = null, ?string $ate = null): array
    {
        $params = [];
        if ($desde) { $params['since'] = $desde; }
        if ($ate)   { $params['until'] = $ate; }
        return $this->get('metrics/engagement', $params)['data'];
    }

    // -----------------------------------------------------------------------
    // Alunos (escopo students:read; nome/RA exigem students:pii)
    // -----------------------------------------------------------------------

    public function alunos(?int $cursoId = null): array
    {
        return $this->get('students', $cursoId ? ['course_id' => $cursoId] : [])['data'];
    }
}
