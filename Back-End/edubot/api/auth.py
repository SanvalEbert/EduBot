# MELHORIA (4.2) — Autenticação e contexto do aluno.
#
# O login original apenas devolvia os IDs e o frontend guardava tudo no
# localStorage; nenhuma requisição posterior era autenticada. Este módulo
# completa a autenticação com um token assinado (HMAC-SHA256, stdlib apenas,
# sem dependências novas):
#
#   1. POST /login passa a emitir um token via generate_token(student_id)
#   2. O frontend envia "Authorization: Bearer <token>" em cada requisição
#   3. Rotas protegidas usam o decorator @require_auth, que valida o token e
#      disponibiliza o aluno logado em flask.g.student — o "contexto do aluno"
#      acessível em qualquer ponto da aplicação (inclusive pelo edubot_agent).
#
# O segredo vem da variável de ambiente EDUBOT_SECRET (defina-a em produção;
# o default existe só para desenvolvimento local).
import os

import base64
import hashlib
import hmac
import json
import secrets
import time
from functools import wraps

from flask import request, g

from edubot.data.models.students import Students

SECRET = os.environ.get("EDUBOT_SECRET", "dev-secret-change-me")
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ---------------------------------------------------------------------------
# Hash de senha (Fase 4d — A5). Stdlib apenas: PBKDF2-HMAC-SHA256 com salt por
# usuário. Formato armazenado: "pbkdf2_sha256$<iterações>$<salt_hex>$<hash_hex>".
# Senhas legadas (texto plano do seed) são aceitas UMA vez e reescritas como
# hash no próprio login (upgrade-on-login) — ver loginRoute.
# ---------------------------------------------------------------------------
PBKDF2_ITERATIONS = 260_000
_HASH_PREFIX = "pbkdf2_sha256$"


def hash_password(password):
    """Gera o hash PBKDF2 com salt aleatório, pronto para armazenar."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()
    return f"{_HASH_PREFIX}{PBKDF2_ITERATIONS}${salt}${digest}"


def is_hashed(stored):
    """True se o valor armazenado já é um hash (não texto plano legado)."""
    return bool(stored) and stored.startswith(_HASH_PREFIX)


def verify_password(password, stored):
    """Confere a senha contra o valor armazenado (hash ou texto plano legado)."""
    if not stored:
        return False
    if not is_hashed(stored):
        # Legado (seed): comparação direta; o chamador deve fazer o upgrade.
        return hmac.compare_digest(password, stored)
    try:
        _, iterations, salt, expected = stored.split("$", 3)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def generate_token(student_id):
    """Builds a signed token: base64(payload).hexdigest(hmac)."""
    payload = {"sid": student_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def verify_token(token):
    """Returns the student_id if the token is valid/unexpired, else None."""
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        # compare_digest avoids timing attacks on the signature comparison
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("sid")
    except Exception:
        return None


def get_current_student():
    """Resolves the logged-in student from the Authorization header (or None)."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    student_id = verify_token(header[len("Bearer "):].strip())
    if student_id is None:
        return None
    return Students.get_or_none(Students.student_id == student_id)


def require_auth(view):
    """Decorator: rejects the request with 401 unless a valid token is sent.

    On success the Student row is exposed as flask.g.student, so any route or
    service in the request cycle can know which student is logged in.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        student = get_current_student()
        if student is None:
            return json.dumps({"Error": "Não autenticado"}), 401
        g.student = student
        return view(*args, **kwargs)
    return wrapper


def is_staff(student):
    """True para tutor/admin — fonte única do papel de gestão pedagógica (A15).

    Antes essa lógica vivia solta em tutorRoute (`_is_tutor`); centralizá-la aqui
    evita divergência entre rotas que precisam distinguir aluno de tutor."""
    role = getattr(student, "role", "aluno") or "aluno"
    return role in ("tutor", "admin") or bool(getattr(student, "is_admin", False))


def require_roles(*allowed):
    """Decorator: exige token válido E papel em `allowed` (ou is_admin) (A.3).

    Uso: `@require_roles("tutor", "admin")`. Falha com 401 (sem token) ou 403
    (papel insuficiente). Expõe g.student como o require_auth."""
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            student = get_current_student()
            if student is None:
                return json.dumps({"Error": "Não autenticado"}), 401
            g.student = student
            role = getattr(student, "role", "aluno") or "aluno"
            if role in allowed or bool(getattr(student, "is_admin", False)):
                return view(*args, **kwargs)
            return json.dumps({"Error": "Acesso restrito"}), 403
        return wrapper
    return deco


# ---------------------------------------------------------------------------
# Rate-limit do login (A.3). In-process, suficiente para 1 réplica de protótipo.
# Guarda contra força bruta: o RA é enumerável e a senha do seed é o próprio RA
# até o primeiro login. Para multi-réplica, mover para um store compartilhado
# (Redis) — documentado no plano.
# ---------------------------------------------------------------------------
import time as _time
from collections import defaultdict, deque

LOGIN_MAX_ATTEMPTS = int(os.environ.get("EDUBOT_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("EDUBOT_LOGIN_WINDOW_SECONDS", "60"))
_login_hits = defaultdict(deque)


def login_throttled(ra, ip):
    """True se (ra, ip) já excedeu LOGIN_MAX_ATTEMPTS na janela. Registra a
    tentativa atual quando ainda dentro do limite."""
    key = f"{ra}|{ip}"
    now = _time.time()
    hits = _login_hits[key]
    while hits and now - hits[0] > LOGIN_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= LOGIN_MAX_ATTEMPTS:
        return True
    hits.append(now)
    return False


def reset_login_throttle():
    """Limpa o estado do rate-limit (usado em testes)."""
    _login_hits.clear()
