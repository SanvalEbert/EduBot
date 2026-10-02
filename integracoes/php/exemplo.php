<?php
/**
 * Exemplo de consumo da API do EduBot a partir de PHP.
 *
 * É o arquivo para entregar à pessoa externa junto com a chave: ele exercita o
 * caminho inteiro (diagnóstico, catálogo, rastreio, métricas) e cada bloco é
 * copiável para o app dela.
 *
 * Rodar pelo terminal:   php exemplo.php
 * Rodar pelo navegador:  http://localhost/edubot/exemplo.php
 *
 * Antes: copie config.php para config.local.php e ponha a chave lá.
 */

require_once __DIR__ . '/edubot_client.php';

$noTerminal = (PHP_SAPI === 'cli');
if (!$noTerminal) {
    header('Content-Type: text/plain; charset=utf-8');
}

function titulo(string $texto): void
{
    echo "\n" . str_repeat('=', 70) . "\n  {$texto}\n" . str_repeat('=', 70) . "\n";
}

$edubot = new EduBotClient();

try {
    // -----------------------------------------------------------------------
    // 1. Diagnóstico — sempre a primeira chamada.
    // -----------------------------------------------------------------------
    titulo('1. Conexão e escopos da chave');
    $ping = $edubot->ping();
    echo "Servidor : {$ping['service']} {$ping['version']}\n";
    echo "Hora     : {$ping['server_time']}\n";
    echo "Chave    : {$ping['key_name']}\n";
    echo "Escopos  : " . implode(', ', $ping['scopes']) . "\n";

    $concedidos = $ping['scopes'];
    $pode = fn(string $escopo): bool => in_array($escopo, $concedidos, true);

    // -----------------------------------------------------------------------
    // 2. Catálogo — o conteúdo da plataforma.
    // -----------------------------------------------------------------------
    if ($pode('catalog:read')) {
        titulo('2. Catálogo de OVAs');
        foreach ($edubot->ovas() as $ova) {
            printf("  #%-3d %-45s gate de quiz: %d%%\n",
                   $ova['ova_id'], mb_substr((string) $ova['ova_name'], 0, 45),
                   $ova['quiz_gate_perc']);
        }

        titulo('3. Questões do OVA 1 (sem gabarito)');
        foreach ($edubot->questoes(1) as $q) {
            printf("  #%-3d [dif %d] %s\n", $q['question_id'], $q['difficulty'],
                   mb_substr((string) $q['statement'], 0, 55));
        }
    }

    // -----------------------------------------------------------------------
    // 3. Rastreio — sincronização incremental por cursor.
    //
    // Este é o padrão a seguir num job recorrente (cron): guarde o último
    // event_id processado; na rodada seguinte só chega o que é novo. Sem isso,
    // cada execução reprocessaria a base inteira.
    // -----------------------------------------------------------------------
    if ($pode('tracking:read')) {
        titulo('4. Eventos de aprendizado (sincronização incremental)');

        $arquivoCursor = __DIR__ . '/.cursor_eventos';
        $ultimoId = file_exists($arquivoCursor) ? (int) file_get_contents($arquivoCursor) : 0;
        echo "Retomando a partir do event_id {$ultimoId}\n\n";

        $processados = 0;
        foreach ($edubot->eventosDesde($ultimoId) as $evento) {
            if ($processados < 10) {   // mostra só os 10 primeiros
                printf("  [%s] aluno %s  %-16s %s#%s\n",
                       $evento['occurred_at'], $evento['subject_id'],
                       $evento['verb'], $evento['object_type'],
                       $evento['object_id'] ?? '-');
            }
            $ultimoId = $evento['event_id'];
            $processados++;
        }
        echo "\n  {$processados} evento(s) novo(s).\n";
        file_put_contents($arquivoCursor, (string) $ultimoId);
        echo "  Cursor salvo em {$ultimoId} — a próxima execução continua daqui.\n";

        titulo('5. Progresso de leitura por OVA');
        foreach ($edubot->progresso(['limit' => 10])['data'] as $p) {
            printf("  aluno %s  OVA %-3d  %4ds de leitura  %3d%% rolado  %s\n",
                   $p['subject_id'], $p['ova_id'], (int) $p['read_time_seconds'],
                   (int) $p['perc_scrolled'], $p['completed'] ? 'concluído' : 'em andamento');
        }
    }

    // -----------------------------------------------------------------------
    // 4. Métricas agregadas — nenhum indivíduo identificado.
    // -----------------------------------------------------------------------
    if ($pode('metrics:read')) {
        titulo('6. Domínio médio por competência (menor primeiro)');
        foreach ($edubot->dominioPorCompetencia() as $m) {
            printf("  %-40s %5.1f%%  (n=%d)\n",
                   mb_substr((string) $m['competencia'], 0, 40),
                   $m['dominio_medio'] * 100, $m['alunos']);
        }

        titulo('7. Questões com pior taxa de acerto');
        $piores = array_slice($edubot->desempenhoPorQuestao(), 0, 5);
        foreach ($piores as $q) {
            printf("  questão #%-4d %5.1f%% de acerto em %d tentativa(s)\n",
                   $q['question_id'], (float) $q['taxa_acerto'] * 100, $q['tentativas']);
        }
    }

    // -----------------------------------------------------------------------
    // 5. Alunos — o formato muda conforme a chave tenha `students:pii` ou não.
    // -----------------------------------------------------------------------
    if ($pode('students:read')) {
        titulo('8. Alunos');
        $alunos = $edubot->alunos();
        foreach (array_slice($alunos, 0, 5) as $a) {
            // `student_name` só existe quando a chave tem students:pii — por
            // isso o ?? e não o acesso direto.
            $identificacao = $a['student_name'] ?? "(pseudonimizado: {$a['subject_id']})";
            printf("  %-32s curso %s  papel %s\n", $identificacao, $a['course_id'], $a['role']);
        }
        if (!$pode('students:pii')) {
            echo "\n  Esta chave não tem `students:pii`: nome e RA não são retornados.\n";
        }
    }

    echo "\nOK — integração funcionando.\n";

} catch (EduBotApiException $e) {
    // A mensagem já vem traduzida pelo cliente (ver EduBotClient::explicar).
    // STDERR só existe no SAPI CLI: no navegador a constante é indefinida e
    // usá-la derrubaria o script justamente no caminho de erro.
    $mensagem = "\nERRO: " . $e->getMessage() . "\n";
    if ($noTerminal) {
        fwrite(STDERR, $mensagem);
    } else {
        echo $mensagem;
    }
    exit(1);
}
