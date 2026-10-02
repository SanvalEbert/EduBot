<?php
/**
 * Configuração do cliente — renomeie este arquivo para `config.local.php`.
 *
 * É o único arquivo que você precisa editar. Preencha os dois valores que o
 * responsável pelo EduBot te enviou (a URL e a chave) e pronto.
 *
 * O `config.php` que veio junto tem também um bloco de credenciais de banco de
 * dados: ele NÃO se aplica a você. Aquele bloco serve para quem hospeda o
 * EduBot, num modo de instalação diferente. Você fala com a API por HTTP e
 * nunca recebe acesso ao banco — é assim por segurança, não por falta de
 * permissão.
 *
 * NÃO comite este arquivo no git do seu projeto: ele contém a chave.
 */

/** URL base que te passaram. Sem barra no final. */
define('EDUBOT_API_BASE', 'https://COLE-A-URL-QUE-TE-PASSARAM');

/** A chave, no formato ek_live_... Trate como senha. */
define('EDUBOT_API_KEY', 'ek_live_COLE-A-CHAVE-AQUI');

/** Segundos até desistir de uma requisição. */
define('EDUBOT_TIMEOUT', 15);

/**
 * Verificação do certificado TLS. Mantenha `true`.
 *
 * Só mude se a URL que te passaram for `http://` num ambiente de teste. Em
 * `https://`, desligar isto faz o cliente aceitar o certificado de qualquer um
 * no meio do caminho — que então lê a sua chave em claro.
 */
define('EDUBOT_VERIFY_TLS', true);
