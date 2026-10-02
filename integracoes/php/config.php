<?php
/**
 * Configuração da integração PHP com o EduBot.
 *
 * ESTE ARQUIVO CONTÉM SEGREDOS. Ele existe no repositório como MODELO: copie
 * para `config.local.php`, preencha lá e mantenha o `config.local.php` fora do
 * git (já está no .gitignore). Nunca comite chave nem senha preenchidas.
 *
 * Precedência (da maior para a menor):
 *   1. config.local.php   (carregado ANTES de tudo, por isso vence)
 *   2. variável de ambiente
 *   3. o default deste arquivo
 *
 * O `config.local.php` é carregado primeiro e as definições abaixo usam
 * `defined()`: em PHP uma constante não pode ser redefinida, então a ordem
 * inversa faria o arquivo local perder para o modelo — silenciosamente em
 * produção e com warning em dev.
 */

// 1) Configuração local (não versionada) tem a palavra final.
if (file_exists(__DIR__ . '/config.local.php')) {
    require __DIR__ . '/config.local.php';
}

/** define() apenas se ainda não houver valor — respeita o config.local.php. */
function edubot_default(string $nome, $valor): void
{
    if (!defined($nome)) {
        define($nome, $valor);
    }
}

// ---------------------------------------------------------------------------
// CAMINHO A — consumir a API Flask do EduBot (recomendado)
// ---------------------------------------------------------------------------

/** Base da API. Local: http://localhost:5010 · Produção: https://seu-dominio */
edubot_default('EDUBOT_API_BASE', getenv('EDUBOT_API_BASE') ?: 'http://localhost:5010');

/**
 * Chave emitida por `python -m tools.apikey_tool criar`.
 * Mostrada UMA vez na criação — o servidor guarda só o hash.
 */
edubot_default('EDUBOT_API_KEY', getenv('EDUBOT_API_KEY') ?: 'ek_live_COLE_A_SUA_CHAVE_AQUI');

/** Segundos até desistir da requisição. */
edubot_default('EDUBOT_TIMEOUT', 15);

/**
 * Verificação do certificado TLS. MANTENHA `true`.
 *
 * Desligar isto faz o cliente aceitar qualquer certificado — inclusive o de
 * alguém no meio do caminho, que então lê a chave de API em claro. Se o seu
 * ambiente usa certificado auto-assinado, a correção é instalar a CA no sistema
 * (ou apontar CURLOPT_CAINFO para o .pem dela), não desligar a verificação.
 */
edubot_default('EDUBOT_VERIFY_TLS', true);

// ---------------------------------------------------------------------------
// CAMINHO B — o PHP fala direto com o MySQL (api.php)
// ---------------------------------------------------------------------------

edubot_default('EDUBOT_DB_HOST', getenv('EDUBOT_DB_HOST') ?: '127.0.0.1');
edubot_default('EDUBOT_DB_PORT', getenv('EDUBOT_DB_PORT') ?: '3310');   // porta do compose
edubot_default('EDUBOT_DB_NAME', getenv('EDUBOT_DB_NAME') ?: 'ova_db');

/**
 * Usuário SOMENTE-LEITURA. Crie com Database/sql/usuario_somente_leitura.sql.
 * Não use `eduardo` nem `root` aqui: o api.php só lê, e a credencial que ele
 * carrega deve ser incapaz de escrever — assim uma falha no script não consegue
 * alterar nem apagar nada.
 */
edubot_default('EDUBOT_DB_USER', getenv('EDUBOT_DB_USER') ?: 'edubot_leitura');
edubot_default('EDUBOT_DB_PASS', getenv('EDUBOT_DB_PASS') ?: 'TROQUE-ESTA-SENHA');

/**
 * Chaves aceitas pelo api.php, no formato 'chave' => 'escopos,separados,por,virgula'.
 *
 * Diferença deliberada em relação ao Flask: aqui as chaves ficam em ARQUIVO, não
 * em banco — o api.php é um script autônomo e cadastrar chave em tabela exigiria
 * escrita, que é justamente o que o usuário somente-leitura não pode fazer.
 * Consequência prática: revogar uma chave é editar este arquivo.
 *
 * Gere valores com:  php -r "echo 'ek_php_'.bin2hex(random_bytes(24)).PHP_EOL;"
 */
edubot_default('EDUBOT_PHP_KEYS', [
    'ek_php_TROQUE_ESTE_VALOR' => 'catalog:read,tracking:read,metrics:read',
]);

/**
 * Salt do pseudônimo. DEVE ser igual ao EDUBOT_PSEUDONYM_SALT do Flask, senão os
 * dois caminhos geram subject_id diferentes para o mesmo aluno e o parceiro não
 * consegue cruzar dados vindos de um com dados vindos do outro.
 */
edubot_default('EDUBOT_PSEUDONYM_SALT', getenv('EDUBOT_PSEUDONYM_SALT') ?: '');
