"""Eventos de aprendizado (D.1) — schema xAPI-lite unificado.

`emit(student, verb, object_type, object_id, **context)` é a entrada única para
gravar um evento a partir do backend (as rotas emitem `answered`,
`received_intervention`, `dismissed`); `POST /events` recebe o lote do frontend
(players, leitura, tutor-chat). Verbos e tipos de objeto são validados contra um
enum — o valor do sinal está em ele ser AGREGÁVEL, ao contrário das strings PT
livres de `interactions`.

Minimização/LGPD (D.5): o texto de uma pergunta ao tutor (`asked_tutor`) só é
guardado com o consentimento `ia_sobre_dados`; sem ele, gravamos o evento com o
texto removido (só metadados). O enforcement é aqui, não na UI.
"""
import datetime
import logging

from edubot.data.models.learning_events import LearningEvents

logger = logging.getLogger("edubot.events")

# Verbos aceitos (xAPI-lite). Mantidos como conjunto para validar o lote do
# front e o uso interno com a MESMA fonte da verdade.
#
# Fase 0 do Plano de Rastreabilidade (P1) — o front JÁ emitia os verbos do
# companheiro de estudo e o object_type `ova_section`, mas eles não estavam
# aqui: `emit_batch` os contava como erro e DESCARTAVA em silêncio. Como o
# painel de engajamento do professor (tutorRoute.consulta `companion_*` e
# `played`/`ova_section`) lê exatamente esses sinais, aquele bloco exibia zero
# para sempre — um painel que afirmava medir algo que o pipeline nunca gravou.
# Registrar os verbos aqui é o que torna a métrica verdadeira.
VERBS = {
    "logged_in", "opened", "read", "played", "paused", "seeked", "completed",
    "answered", "asked_tutor", "received_intervention", "dismissed",
    # Companheiro de estudo (Plano 3) — emitidos por useCompanionScript/OvaReader.
    "companion_spoke", "companion_listened", "companion_dismissed", "companion_explain",
    # Mídia: velocidade de reprodução (Fase 1 — vídeo real).
    "rate_changed",
    # Presença/atenção: janelas de ociosidade da sessão de leitura (Fase 2).
    "idle_start", "idle_end",
    # Leitura por seção do OVA (Fase 2) — a linha do tempo que mostra ONDE o
    # aluno travou. O volume por sessão é baixo (transições, não amostragem).
    "section_enter", "section_exit",
}
OBJECT_TYPES = {"ova", "ova_section", "resource", "question", "intervention", "session"}

# Verbos cujo `context.text` é dado pessoal sensível (conteúdo livre do aluno):
# só persistem o texto com consentimento explícito de IA sobre os dados (D.5).
_TEXT_CONSENT_VERBS = {"asked_tutor"}

MAX_BATCH = 50


def _student_id(student):
    return getattr(student, "student_id", student)


def _minimize_context(student, verb, context):
    """Remove `text` de verbos sensíveis quando falta consentimento (D.5).

    Importa `consents` de forma preguiçosa para não acoplar o import de eventos
    ao de consentimento (e para o serviço funcionar mesmo antes da migration_007
    ter rodado — nesse caso, sem consentimento registrado, remove o texto)."""
    if not context or verb not in _TEXT_CONSENT_VERBS or "text" not in context:
        return context
    try:
        from edubot.services.consents import has_consent
        allowed = has_consent(student, "ia_sobre_dados")
    except Exception:
        allowed = False
    if allowed:
        return context
    minimized = dict(context)
    minimized["text"] = None
    return minimized


def emit(student, verb, object_type, object_id=None, occurred_at=None, **context):
    """Grava um evento. Best-effort: nunca quebra a requisição principal.

    Retorna a linha criada ou None. Verbo/tipo inválidos são logados e ignorados
    (uso interno é confiável; o lote do front é validado na rota antes de chegar
    aqui). `context` é opcional; chaves úteis: perc, seconds, correct,
    response_ms, session_id, text."""
    try:
        if verb not in VERBS or object_type not in OBJECT_TYPES:
            logger.warning("Evento ignorado (verbo/tipo inválido): %s/%s", verb, object_type)
            return None
        ctx = _minimize_context(student, verb, context or None)
        return LearningEvents.create(
            student_id=_student_id(student),
            verb=verb,
            object_type=object_type,
            object_id=object_id,
            context=ctx,
            occurred_at=occurred_at or datetime.datetime.now(),
        )
    except Exception:
        logger.exception("Falha ao gravar evento %s/%s", verb, object_type)
        return None


def emit_batch(student, events):
    """Grava um lote validado (usado por POST /events). Retorna (aceitos, erros).

    Cada item: {verb, object_type, object_id?, context?, occurred_at?}. Itens com
    verbo/tipo inválido são contados como erro e não gravados; o lote não falha
    por um item ruim (robustez do sync do front)."""
    accepted, errors = 0, 0
    for ev in events[:MAX_BATCH]:
        verb = ev.get("verb")
        object_type = ev.get("object_type")
        if verb not in VERBS or object_type not in OBJECT_TYPES:
            errors += 1
            continue
        occurred_at = _parse_dt(ev.get("occurred_at"))
        row = emit(student, verb, object_type, ev.get("object_id"),
                   occurred_at=occurred_at, **(ev.get("context") or {}))
        if row is not None:
            accepted += 1
        else:
            errors += 1
    return accepted, errors


def _parse_dt(value):
    """Converte o timestamp ISO do front em datetime LOCAL naive, ou None.

    O front manda `new Date().toISOString()` (UTC, sufixo Z). O resto do banco
    usa datetime.now() (hora local, naive); descartar o fuso gravaria o relógio
    UTC como se fosse local — no Brasil, eventos 3h "no futuro", o suficiente
    para virar a fronteira de dia da inatividade e das janelas de outcome (B.6).
    Aqui o timestamp é CONVERTIDO para o fuso local antes de perder o tzinfo."""
    if not value:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt
