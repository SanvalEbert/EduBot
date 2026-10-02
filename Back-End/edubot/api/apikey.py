"""Autenticação de SISTEMA externo por chave de API (integração com parceiros).

Por que não reusar o `auth.py`: aquele token carrega um `student_id` e existe
para o aluno logado no front. Um parceiro (app PHP, BI, piloto de pesquisa) não
tem aluno — ele tem uma credencial de máquina, de vida longa, com um recorte
explícito do que pode ler. São conceitos diferentes e ficam separados de
propósito: nenhuma chave de parceiro vira sessão de aluno, e nenhuma sessão de
aluno vira acesso de parceiro.

Contrato:

    Header:  X-API-Key: ek_live_<44 chars>
             (ou  Authorization: ApiKey ek_live_<...>  — mesma coisa, para
              clientes que só sabem mandar Authorization)

    401  chave ausente, desconhecida, revogada ou expirada
    403  chave válida, mas sem o escopo exigido pelo endpoint
    429  chave estourou o teto de requisições na janela

O segredo nunca é armazenado em claro: guardamos o SHA-256 (a chave tem 264 bits
de entropia vinda do `secrets`, então não há o que brute-forçar — não é senha de
humano, PBKDF2 aqui só encareceria o caminho quente sem ganho real).

ESCOPOS — a fonte da verdade é o dict SCOPES abaixo. `students:pii` é o único que
libera nome/RA e está separado a propósito: conceder rastreio não concede dado
pessoal junto.
"""
import datetime
import hashlib
import json
import os
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import request, g

from edubot.data.models.api_keys import ApiKeys

KEY_PREFIX = "ek_live_"       # torna a chave reconhecível em log e em busca de segredo vazado
PREFIX_LEN = 16               # quanto do segredo guardamos em claro para identificar a linha

SCOPES = {
    "catalog:read":  "OVAs, competências, questões e cursos (conteúdo, sem dado pessoal)",
    "tracking:read": "Eventos de aprendizado e progresso, com aluno PSEUDONIMIZADO",
    "metrics:read":  "Métricas agregadas por turma/competência (sem indivíduo)",
    "students:read": "Lista de alunos pseudonimizada (subject_id, curso, papel)",
    "students:pii":  "DADO PESSOAL: nome e RA do aluno. Exige base legal — LGPD",
    "events:write":  "GRAVAR eventos pelo edubot-tracker.js (chave PÚBLICA: vai no HTML)",
}

# Escopos que só fazem sentido numa chave que fica no SERVIDOR do parceiro. Uma
# chave `events:write` é embutida no HTML do material e qualquer visitante a lê
# no código-fonte — se ela também lesse, o rastreio da turma inteira ficaria
# público. O apikey_tool recusa a mistura.
READ_SCOPES = {s for s in SCOPES if s != "events:write"}

# Teto por chave. Não é proteção contra DDoS (isso é camada de rede); é o freio
# que impede um parceiro com loop errado de varrer a base inteira sem parar.
RATE_LIMIT = int(os.environ.get("EDUBOT_APIKEY_RATE_LIMIT", "120"))
RATE_WINDOW = int(os.environ.get("EDUBOT_APIKEY_RATE_WINDOW", "60"))
_hits = defaultdict(deque)

# Pseudonimização (LGPD art. 12): o parceiro recebe um identificador estável e
# opaco no lugar do student_id. Estável porque ele precisa correlacionar eventos
# do MESMO aluno ao longo do tempo; opaco porque não deve conseguir voltar ao
# aluno sem o segredo. Trocar EDUBOT_PSEUDONYM_SALT rotaciona todos os pseudônimos.
_PSEUDONYM_SALT = os.environ.get("EDUBOT_PSEUDONYM_SALT", "")


def hash_key(raw):
    """SHA-256 hex do segredo — é isto que fica no banco e o que buscamos."""
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_key():
    """Gera uma chave nova. Retorna (segredo_em_claro, prefixo, hash).

    O segredo em claro só existe aqui e no retorno: quem chama mostra uma vez ao
    operador e descarta. Não há caminho de recuperação — chave perdida se revoga
    e se emite outra."""
    raw = KEY_PREFIX + secrets.token_urlsafe(33)
    return raw, raw[:PREFIX_LEN], hash_key(raw)


def pseudonym(student_id):
    """Pseudônimo estável e opaco do aluno, para consumo externo.

    Sem salt configurado o valor ainda é estável (o parceiro consegue agrupar),
    mas é derivável por qualquer um que conheça o esquema — por isso o
    EDUBOT_PSEUDONYM_SALT deve ser definido em produção, como o EDUBOT_SECRET."""
    return hashlib.sha256(f"{_PSEUDONYM_SALT}:{student_id}".encode()).hexdigest()[:16]


def _extract_key():
    """Lê a chave do header. Aceita X-API-Key ou Authorization: ApiKey <...>."""
    raw = request.headers.get("X-API-Key", "").strip()
    if raw:
        return raw
    header = request.headers.get("Authorization", "").strip()
    if header.lower().startswith("apikey "):
        return header[7:].strip()
    return ""


def rate_limited(key_id, limit=None, bucket=""):
    """True se a chave já estourou `limit` na janela. Registra o hit quando
    ainda dentro do teto (mesma mecânica do login_throttled do auth.py).

    `bucket` separa contadores da mesma chave com tetos diferentes — a coleta do
    tracker (um material com a turma inteira aberta) precisa de um teto maior
    que a leitura de um parceiro."""
    limit = RATE_LIMIT if limit is None else limit
    now = time.time()
    hits = _hits[(bucket, key_id)]
    while hits and now - hits[0] > RATE_WINDOW:
        hits.popleft()
    if len(hits) >= limit:
        return True
    hits.append(now)
    return False


def touch_usage(key):
    """Contabiliza o uso da chave. UPDATE direto (não .save()) para não reescrever
    as demais colunas e não competir com uma edição concorrente da chave."""
    (ApiKeys
     .update(last_used_at=datetime.datetime.now(),
             request_count=ApiKeys.request_count + 1)
     .where(ApiKeys.key_id == key.key_id)
     .execute())


def reset_rate_limit():
    """Zera o estado do rate-limit (usado nos testes)."""
    _hits.clear()


def resolve_key(raw):
    """Devolve a linha da chave se ela for válida AGORA, senão None.

    Válida = existe, `active`, e não expirada. A checagem de expiração é feita em
    Python e não no WHERE porque `expires_at` é NULL na maioria das linhas e a
    comparação com NULL em SQL descartaria justamente as chaves sem validade."""
    if not raw:
        return None
    row = ApiKeys.get_or_none((ApiKeys.key_hash == hash_key(raw)) & (ApiKeys.active == True))
    if row is None:
        return None
    if row.expires_at and row.expires_at < datetime.datetime.now():
        return None
    return row


def _error(message, status):
    return json.dumps({"error": message, "status": status}), status, \
        {"Content-Type": "application/json"}


def require_api_key(*required_scopes):
    """Decorator: exige chave válida E todos os escopos listados.

    Uso:  @require_api_key("tracking:read")

    Expõe a chave em `flask.g.api_key`, para o endpoint decidir o nível de
    detalhe (é assim que `students:pii` liga nome/RA sem precisar de outra rota).
    """
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            key = resolve_key(_extract_key())
            if key is None:
                return _error("Chave de API ausente, inválida ou revogada.", 401)
            if rate_limited(key.key_id):
                return _error(
                    f"Limite de {RATE_LIMIT} requisições por {RATE_WINDOW}s excedido.", 429)
            granted = key.scope_list()
            faltando = [s for s in required_scopes if s not in granted]
            if faltando:
                return _error(
                    f"Chave sem permissão. Escopo(s) necessário(s): {', '.join(faltando)}.", 403)
            g.api_key = key
            touch_usage(key)
            return view(*args, **kwargs)
        return wrapper
    return deco


def has_scope(scope):
    """True se a chave do request corrente tem o escopo. Para decisões DENTRO do
    endpoint — tipicamente `students:pii`, que muda o payload, não o acesso."""
    key = getattr(g, "api_key", None)
    return bool(key) and scope in key.scope_list()
