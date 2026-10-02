"""Consentimento (D.5) — base legal e enforcement no backend.

`has_consent(student, purpose)` é o guard usado pelos caminhos que dependem de
opt-in: o texto das perguntas ao tutor (`events.emit` de `asked_tutor`) e os
ramos de LLM sobre os dados do aluno (coach/tutor/recomendação com IA real).
`set_consent` faz o upsert (grant/revoke com timestamp).

Política de finalidades:
  tracking_pedagogico  base legal = execução de contrato educacional. Informado,
                       não opcional: default concedido (o serviço É o
                       rastreamento). Nunca bloqueia o tracking pedagógico.
  ia_sobre_dados       opt-in revogável. SEM ele: sem texto de pergunta guardado
                       e o agente roda só regras/templates (sem LLM) para o aluno.
  imagem_voz           opt-in revogável (virtualização — V.x).
"""
import datetime
import logging

from edubot.data.models.consents import Consents

logger = logging.getLogger("edubot.consents")

# Finalidades válidas. `default_granted`: tracking é informado/execução de
# contrato — na ausência de linha, considera-se concedido (não é opt-in).
PURPOSES = {
    "tracking_pedagogico": {"default_granted": True, "opt_in": False},
    "ia_sobre_dados": {"default_granted": False, "opt_in": True},
    "imagem_voz": {"default_granted": False, "opt_in": True},
    # G.4 (Plano 2): participar do ranking da turma expõe apelido + XP aos colegas
    # — finalidade nova, opt-in revogável. Sem migration: a tabela consents é
    # genérica. Revogar esconde o aluno do ranking imediatamente.
    "ranking_turma": {"default_granted": False, "opt_in": True},
}


def _student_id(student):
    return getattr(student, "student_id", student)


def has_consent(student, purpose):
    """Estado atual do consentimento (bool). Sem linha registrada, cai no default
    da finalidade. Best-effort: se a consulta falhar (ex.: migration_007 ainda
    não rodou), retorna o default — nunca levanta para o chamador."""
    meta = PURPOSES.get(purpose, {"default_granted": False})
    try:
        row = Consents.get_or_none((Consents.student_id == _student_id(student)) &
                                   (Consents.purpose == purpose))
    except Exception:
        return meta["default_granted"]
    if row is None:
        return meta["default_granted"]
    return bool(row.granted)


def set_consent(student, purpose, granted):
    """Upsert do consentimento. `tracking_pedagogico` não pode ser revogado (é
    condição do serviço) — a revogação é ignorada e mantida como concedida.
    Retorna a linha resultante (ou None em finalidade inválida)."""
    if purpose not in PURPOSES:
        return None
    if purpose == "tracking_pedagogico":
        granted = True  # informado, não opcional
    now = datetime.datetime.now()
    sid = _student_id(student)
    row = Consents.get_or_none((Consents.student_id == sid) &
                               (Consents.purpose == purpose))
    if row is None:
        return Consents.create(student_id=sid, purpose=purpose, granted=bool(granted),
                               granted_at=now, revoked_at=None)
    row.granted = bool(granted)
    if granted:
        row.granted_at = now
        row.revoked_at = None
    else:
        row.revoked_at = now
    row.save()
    return row


def current_consents(student):
    """Estado das 3 finalidades para o aluno (alimenta GET /consents e a tela
    'Meus dados'). Inclui as que ainda não têm linha (com o default)."""
    sid = _student_id(student)
    rows = {c.purpose: c for c in Consents.select().where(Consents.student_id == sid)}
    out = []
    for purpose, meta in PURPOSES.items():
        row = rows.get(purpose)
        out.append({
            "purpose": purpose,
            "granted": bool(row.granted) if row else meta["default_granted"],
            "opt_in": meta["opt_in"],
            "granted_at": str(row.granted_at) if row and row.granted_at else None,
            "revoked_at": str(row.revoked_at) if row and row.revoked_at else None,
        })
    return out
