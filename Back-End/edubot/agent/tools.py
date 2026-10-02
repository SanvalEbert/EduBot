# MELHORIA (OVA personalizada) — Ferramentas (tools) do agente EduBot.
#
# O EduBot deixa de ser um classificador de uma chamada só e passa a ser um
# AGENTE com tool-use: ele inspeciona o desempenho do aluno, consulta o banco de
# conteúdo (recursos + questões) por competência e MONTA uma OVA de reforço.
#
# Cada tool tem:
#   - um JSON-schema (formato `tools` da Anthropic Messages API / Bedrock), e
#   - uma função Python pura que executa a ação contra o banco.
#
# As funções recebem `ctx` (contém o aluno logado, resolvido do token na rota —
# NUNCA do payload) para impedir que o agente leia/escreva dados de outro aluno.
# IDs escolhidos pelo modelo são SEMPRE validados antes de persistir.


import datetime

from edubot.data.models.competencies import Competencies
from edubot.data.models.subjects import Subjects
from edubot.data.models.offerings import Offerings
from edubot.data.models.questions import Questions
from edubot.data.models.answers import Answers
from edubot.data.models.attempts import Attempts
from edubot.data.models.resources import Resources
from edubot.data.models.personalized_ova import PersonalizedOVA, PersonalizedOVAItem

# Limiar de competência desenvolvida (mesmo critério do student_context)
COMPETENCY_DEVELOPED_RATIO = 0.8


# ---------------------------------------------------------------------------
# JSON-schemas das tools (o que é enviado ao modelo)
# ---------------------------------------------------------------------------
TOOLS_SCHEMA = [
    {
        "name": "listar_competencias_fracas",
        "description": (
            "Lista as competências do curso do aluno ordenadas da mais fraca "
            "para a mais forte, com status (não iniciada / em desenvolvimento / "
            "desenvolvida) e taxa de erro no quiz por competência. Use primeiro, "
            "para descobrir QUAL assunto remediar."),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "listar_recursos_remediacao",
        "description": (
            "Lista os recursos (vídeos, textos, podcasts) do banco de conteúdo "
            "associados a uma competência. São os materiais candidatos a compor "
            "a OVA de reforço daquele assunto."),
        "input_schema": {
            "type": "object",
            "properties": {
                "competency_id": {"type": "integer", "description": "Competência-alvo."},
                "tipo": {
                    "type": "string",
                    "enum": ["video", "texto", "podcast"],
                    "description": "Opcional: filtra por tipo de mídia."},
            },
            "required": ["competency_id"],
        },
    },
    {
        "name": "listar_questoes_reforco",
        "description": (
            "Lista as questões do banco associadas a uma competência (sem o "
            "gabarito), candidatas a compor o quiz da OVA de reforço."),
        "input_schema": {
            "type": "object",
            "properties": {
                "competency_id": {"type": "integer", "description": "Competência-alvo."},
            },
            "required": ["competency_id"],
        },
    },
    {
        "name": "criar_ova_personalizada",
        "description": (
            "Monta e PERSISTE a OVA de reforço para o aluno, a partir dos "
            "recursos e questões escolhidos. Chame por último, uma única vez. "
            "Retorna o id da OVA criada."),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_competency_id": {"type": "integer"},
                "titulo": {"type": "string"},
                "mensagem_aluno": {
                    "type": "string",
                    "description": "Mensagem motivacional dirigida ao aluno pelo nome."},
                "justificativa": {
                    "type": "string",
                    "description": "Por que esta OVA foi gerada (para o professor)."},
                "resource_ids": {
                    "type": "array", "items": {"type": "integer"},
                    "description": "IDs dos recursos a incluir (na ordem desejada)."},
                "question_ids": {
                    "type": "array", "items": {"type": "integer"},
                    "description": "IDs das questões de reforço a incluir."},
            },
            "required": ["target_competency_id", "titulo", "mensagem_aluno",
                         "justificativa", "resource_ids", "question_ids"],
        },
    },
]


# ---------------------------------------------------------------------------
# Implementações
# ---------------------------------------------------------------------------
def _course_competencies(student):
    return (Competencies
            .select()
            .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id))
            .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
            .where(Offerings.course_id == student.course_id))


def listar_competencias_fracas(ctx, **_):
    student = ctx["student"]
    # D.2: mastery por competência (BKT) — sinal mais estável que a taxa de erro.
    from edubot.services.mastery import mastery_map, status_from_mastery
    pm = mastery_map(student.student_id)
    rows = []
    for comp in _course_competencies(student):
        total = Questions.select().where(Questions.competency_id == comp.competency_id).count()
        correct = (Answers
                   .select()
                   .join(Questions, on=(Answers.question_id == Questions.question_id))
                   .where((Answers.student_id == student) &
                          (Questions.competency_id == comp.competency_id))
                   .count())
        comp_questions = Questions.select(Questions.question_id).where(
            Questions.competency_id == comp.competency_id)
        att_total = (Attempts.select()
                     .where((Attempts.student_id == student) &
                            (Attempts.question_id.in_(comp_questions))).count())
        att_wrong = (Attempts.select()
                     .where((Attempts.student_id == student) &
                            (Attempts.question_id.in_(comp_questions)) &
                            (Attempts.is_correct == False)).count())
        taxa_erro = round(att_wrong / att_total, 2) if att_total else None
        # D.2: domínio estimado por BKT quando disponível; senão, razão
        # acertos/total (degradação segura, igual ao perfil).
        p_mastery = pm.get(comp.competency_id)
        if p_mastery is not None:
            status = status_from_mastery(p_mastery)
            dominio = p_mastery
        else:
            dominio = (correct / total) if total else 0
            if total == 0 or correct == 0:
                status = "não iniciada"
            elif dominio >= COMPETENCY_DEVELOPED_RATIO:
                status = "desenvolvida"
            else:
                status = "em desenvolvimento"
        rows.append({
            "competency_id": comp.competency_id,
            "nome": comp.competency_description,
            "status": status,
            "acertos": correct,
            "total_questoes": total,
            "taxa_erro": taxa_erro,
            "dominio_estimado": round(dominio, 2) if p_mastery is not None else None,
            "fraca": status != "desenvolvida",
            # ordenação: menor domínio primeiro (mais fraca); desempate por taxa
            # de erro. p_mastery domina quando existe (sinal mais estável).
            "_score": (dominio, -(taxa_erro or 0.0)),
        })
    # mais fraca primeiro: MENOR domínio, depois MAIOR taxa de erro
    rows.sort(key=lambda r: r["_score"])
    for r in rows:
        r.pop("_score", None)
    return {"competencias": rows}


def listar_recursos_remediacao(ctx, competency_id=None, tipo=None, **_):
    query = Resources.select().where(Resources.competency_id == competency_id)
    if tipo:
        query = query.where(Resources.resource_type == tipo)
    recursos = [{
        "resource_id": r.resource_id,
        "titulo": r.resource_title,
        "tipo": r.resource_type,
        "url": r.resource_url,
        "media_type": r.media_type,
    } for r in query]

    # P.2 — ordena pelo formato em que o aluno mais APRENDE (preferences, P.1):
    # o recurso do formato preferido vem primeiro, para a trilha de reforço
    # COMEÇAR por ele. Estável (preserva a ordem original dentro de cada grupo);
    # sem preferência confiável, mantém a ordem do banco (degradação segura).
    student = ctx.get("student")
    formato_pref = None
    if student is not None:
        from edubot.services.preferences import preferred_format
        formato_pref = preferred_format(getattr(student, "student_id", student),
                                        ctx.get("profile"))
    if formato_pref:
        recursos.sort(key=lambda r: 0 if r["tipo"] == formato_pref else 1)

    return {
        "competency_id": competency_id,
        "recursos": recursos,
        # o modelo "vê" a preferência para decidir a ordem da trilha; o mock usa
        # o MESMO sinal (comportamento de referência igual com e sem LLM).
        "formato_preferido_do_aluno": formato_pref,
    }


def listar_questoes_reforco(ctx, competency_id=None, **_):
    # Nunca devolve o gabarito (mesma política de B9/questionRoute).
    questoes = [{
        "question_id": q.question_id,
        "enunciado": q.statement,
    } for q in Questions.select().where(Questions.competency_id == competency_id)]
    return {"competency_id": competency_id, "questoes": questoes}


def criar_ova_personalizada(ctx, target_competency_id=None, titulo="OVA de reforço",
                            mensagem_aluno="", justificativa="",
                            resource_ids=None, question_ids=None, **_):
    student = ctx["student"]
    resource_ids = resource_ids or []
    question_ids = question_ids or []

    # VALIDAÇÃO: só persiste itens que existem E pertencem à competência-alvo,
    # para o agente não conseguir inventar IDs nem misturar assuntos.
    valid_resources = [
        r.resource_id for r in Resources.select(Resources.resource_id).where(
            (Resources.resource_id.in_(resource_ids)) &
            (Resources.competency_id == target_competency_id))
    ] if resource_ids else []
    valid_questions = [
        q.question_id for q in Questions.select(Questions.question_id).where(
            (Questions.question_id.in_(question_ids)) &
            (Questions.competency_id == target_competency_id))
    ] if question_ids else []

    if not valid_resources and not valid_questions:
        return {"error": "Nenhum recurso/questão válido para a competência-alvo."}

    # Preserva a ordem pedida pelo modelo
    valid_resources = [rid for rid in resource_ids if rid in set(valid_resources)]
    valid_questions = [qid for qid in question_ids if qid in set(valid_questions)]

    pova = PersonalizedOVA.create(
        student_id=student,
        target_competency_id=target_competency_id,
        title=titulo,
        message=mensagem_aluno,
        rationale=justificativa,
        status="ativa",
        created_at=datetime.datetime.now(),
    )
    position = 0
    for rid in valid_resources:
        PersonalizedOVAItem.create(personalized_ova_id=pova, item_kind="resource",
                                   resource_id=rid, position=position)
        position += 1
    for qid in valid_questions:
        PersonalizedOVAItem.create(personalized_ova_id=pova, item_kind="question",
                                   question_id=qid, position=position)
        position += 1

    return {
        "personalized_ova_id": pova.personalized_ova_id,
        "titulo": titulo,
        "target_competency_id": target_competency_id,
        "itens_recursos": len(valid_resources),
        "itens_questoes": len(valid_questions),
    }


# ---------------------------------------------------------------------------
# B.3 — tools novas do catálogo unificado (leitura + escrita com tiers).
# A IDEMPOTÊNCIA vive DENTRO da tool: o modelo não consegue duplicar nem
# repetindo a chamada (fonte única do dedup, antes espalhado na proatividade).
# ---------------------------------------------------------------------------
def obter_perfil_resumido(ctx, **_):
    """Digest do perfil do aluno (para o agente perceber o estado sem despejar o
    perfil inteiro no prompt). Minimizado — primeiro nome, sem RA."""
    from edubot.services.student_context import build_student_profile
    student = ctx["student"]
    profile = ctx.get("profile") or build_student_profile(student)
    est = profile.get("estudante", {}) or {}
    comps = profile.get("competencias", [])
    fraca = None
    if comps:
        fraca = min(comps, key=lambda c: c.get("dominio_estimado")
                    if c.get("dominio_estimado") is not None else 1.0)
    return {
        "primeiro_nome": (est.get("nome") or "").split(" ")[0],
        "dias_sem_acesso": profile.get("dias_sem_acesso"),
        "percentual_consumido": profile.get("recursos", {}).get("percentual_consumido"),
        "taxa_erro_quiz": profile.get("quiz", {}).get("taxa_erro"),
        "competencia_mais_fraca": fraca["nome"] if fraca else None,
        "competencia_mais_fraca_id": fraca["competency_id"] if fraca else None,
    }


def historico_intervencoes(ctx, limite=8, **_):
    """B.6 — histórico recente das decisões do agente para o aluno, COM o outcome
    (aceita/dispensada/melhorou/expirada/pendente). É como o agente evita repetir
    o que não funcionou: se muitas foram dispensadas, ele deve variar a abordagem."""
    from edubot.data.models.agent_decisions import AgentDecisions
    from edubot.services.outcomes import outcomes_summary

    student = ctx["student"]
    ultimas = []
    for d in (AgentDecisions
              .select()
              .where(AgentDecisions.student_id == student.student_id)
              .order_by(AgentDecisions.created_at.desc())
              .limit(int(limite or 8))):
        digest = d.input_digest or {}
        ultimas.append({
            "tipo": digest.get("tipo"),
            "trigger": d.trigger_type,
            "outcome": d.outcome or "pendente",
            "data": str(d.created_at)[:10],
        })
    return {"resumo": outcomes_summary(student.student_id), "ultimas": ultimas}


def criar_intervencao(ctx, tipo="", mensagem_aluno="", prioridade="media", **_):
    """Cria uma intervenção para o aluno (o EduBot 'fala primeiro'). IDEMPOTENTE:
    dedup por (aluno, tipo, hoje) enquanto pendente — fonte única do dedup que
    antes vivia na proatividade."""
    import datetime
    from edubot.data.models.interventions import Interventions
    from edubot.services.events import emit

    student = ctx["student"]
    tipo = (tipo or "").strip() or "recomendacao"
    if not (mensagem_aluno or "").strip():
        return {"error": "mensagem_aluno é obrigatória."}
    today = datetime.date.today()
    existing = (Interventions
                .select()
                .where((Interventions.student_id == student) &
                       (Interventions.date == today) &
                       (Interventions.type == tipo) &
                       (Interventions.result == "pendente"))
                .first())
    if existing is not None:
        return {"intervention_id": existing.intervention_id, "tipo": tipo, "dedup": True}
    it = Interventions.create(student_id=student, date=today, type=tipo,
                              description=mensagem_aluno, result="pendente")
    emit(student, "received_intervention", "intervention", it.intervention_id,
         tipo=tipo, trigger="agent_tool")
    return {"intervention_id": it.intervention_id, "tipo": tipo, "prioridade": prioridade}


def agendar_revisao(ctx, competency_id=None, days_from_now=3, **_):
    """Agenda (ou reagenda) a revisão espaçada de uma competência do curso do
    aluno (D.3). Valida que a competência é do curso do aluno (mesma política de
    validação de IDs escolhidos pelo modelo). IDEMPOTENTE via a unique da tabela."""
    from edubot.services.reviews import schedule
    student = ctx["student"]
    valid = {c.competency_id for c in _course_competencies(student)}
    if competency_id not in valid:
        return {"error": "Competência não pertence ao curso do aluno."}
    row = schedule(student.student_id, competency_id,
                   days_from_now=int(days_from_now or 3), created_by="agent")
    return {"review_id": row.review_id, "competency_id": competency_id,
            "due_date": str(row.due_date), "interval_days": row.interval_days}


# ---------------------------------------------------------------------------
# B.5 — ações novas com tiers de autonomia mais altos.
# `ajustar_dificuldade` (auto_capped): efeito real via student_difficulty (D.4).
# `alertar_tutor` (auto_or_queue): severidade alta cai na FILA de aprovação.
# `propor_mensagem_do_tutor` (queue): NUNCA sai sem o tutor aprovar.
# ---------------------------------------------------------------------------
def ajustar_dificuldade(ctx, competency_id=None, delta=0, **_):
    """Ajusta o nível-alvo de dificuldade do aluno numa competência (±1). TETO:
    1 mudança por dia por competência (validado aqui, não no prompt). Nível fica
    em [1,3]. Valida que a competência é do curso do aluno."""
    import datetime
    from edubot.data.models.student_difficulty import StudentDifficulty

    student = ctx["student"]
    valid = {c.competency_id for c in _course_competencies(student)}
    if competency_id not in valid:
        return {"error": "Competência não pertence ao curso do aluno."}
    try:
        delta = int(delta)
    except (TypeError, ValueError):
        return {"error": "delta inválido."}
    if delta not in (-1, 1):
        return {"error": "delta deve ser -1 ou +1 (máx. 1 nível por vez)."}

    today = datetime.date.today()
    row = StudentDifficulty.get_or_none(
        (StudentDifficulty.student_id == student.student_id) &
        (StudentDifficulty.competency_id == competency_id))
    if row is not None and row.updated_at and row.updated_at.date() == today:
        return {"error": "Dificuldade já ajustada hoje para esta competência (teto 1/dia).",
                "level": row.level}

    current = row.level if row is not None else 2
    new_level = max(1, min(3, current + delta))
    now = datetime.datetime.now()
    if row is None:
        StudentDifficulty.create(student_id=student.student_id, competency_id=competency_id,
                                 level=new_level, updated_at=now)
    else:
        row.level = new_level
        row.updated_at = now
        row.save()
    return {"competency_id": competency_id, "level": new_level, "delta": delta}


def alertar_tutor(ctx, tipo="", mensagem="", severidade="media", **_):
    """Cria um alerta para o tutor. Severidade baixa|media → alerta informativo
    direto (fluxo atual). Severidade ALTA → entra na FILA de aprovação
    (status='aguardando_aprovacao') e NÃO notifica o aluno. Dedup por
    (aluno, tipo) enquanto não lido."""
    import datetime
    from edubot.data.models.alerts import Alerts

    student = ctx["student"]
    tipo = (tipo or "").strip() or "risco"
    if not (mensagem or "").strip():
        return {"error": "mensagem é obrigatória."}
    severidade = severidade if severidade in ("alta", "media", "baixa") else "media"

    existing = (Alerts
                .select()
                .where((Alerts.student_id == student) & (Alerts.type == tipo) &
                       (Alerts.read == False))
                .first())
    if existing is not None:
        return {"alert_id": existing.alert_id, "tipo": tipo, "dedup": True}

    status = "aguardando_aprovacao" if severidade == "alta" else "aberto"
    a = Alerts.create(student_id=student, type=tipo,
                      message=f"{student.student_name}: {mensagem}",
                      severity=severidade, created_at=datetime.datetime.now(),
                      read=False, status=status)
    return {"alert_id": a.alert_id, "tipo": tipo, "severidade": severidade, "status": status}


def propor_mensagem_do_tutor(ctx, mensagem_aluno="", justificativa="", **_):
    """Propõe uma mensagem que O TUTOR enviaria ao aluno. SEMPRE entra na fila
    (tier queue): nada é enviado ao aluno sem aprovação. Na aprovação vira uma
    intervenção assinada 'do seu tutor'."""
    import datetime
    from edubot.data.models.alerts import Alerts

    student = ctx["student"]
    if not (mensagem_aluno or "").strip():
        return {"error": "mensagem_aluno é obrigatória."}
    # IDEMPOTÊNCIA (mesma política das demais tools de escrita): enquanto houver
    # uma proposta deste aluno aguardando o tutor, não empilha outra — o agente
    # não consegue lotar a fila repetindo a chamada em execuções sucessivas.
    existing = (Alerts
                .select()
                .where((Alerts.student_id == student) &
                       (Alerts.type == "mensagem_proposta") &
                       (Alerts.status == "aguardando_aprovacao"))
                .first())
    if existing is not None:
        return {"alert_id": existing.alert_id, "status": "aguardando_aprovacao",
                "queued": True, "dedup": True}
    a = Alerts.create(
        student_id=student, type="mensagem_proposta",
        message=f"Mensagem proposta para {student.student_name}",
        severity="media", created_at=datetime.datetime.now(), read=False,
        status="aguardando_aprovacao",
        proposed_action={"type": "intervencao_do_tutor",
                         "mensagem_aluno": mensagem_aluno,
                         "justificativa": justificativa})
    return {"alert_id": a.alert_id, "status": "aguardando_aprovacao", "queued": True}


# Registro nome -> função, usado pelo loop do agente.
TOOL_FUNCTIONS = {
    "listar_competencias_fracas": listar_competencias_fracas,
    "listar_recursos_remediacao": listar_recursos_remediacao,
    "listar_questoes_reforco": listar_questoes_reforco,
    "criar_ova_personalizada": criar_ova_personalizada,
    "obter_perfil_resumido": obter_perfil_resumido,
    "historico_intervencoes": historico_intervencoes,
    "criar_intervencao": criar_intervencao,
    "agendar_revisao": agendar_revisao,
    "ajustar_dificuldade": ajustar_dificuldade,
    "alertar_tutor": alertar_tutor,
    "propor_mensagem_do_tutor": propor_mensagem_do_tutor,
}

# B.3 — catálogo unificado com METADADO DE AUTONOMIA (tier). O tier é política
# de execução (quem pode rodar sozinho vs. quem entra em fila de aprovação — B.5);
# hoje documenta a intenção e é usado pelos testes/observabilidade.
#   read          — leitura, livre
#   auto          — escrita reversível/interna/idempotente, autônoma
#   auto_capped   — escrita autônoma com teto (ex.: ±1 nível/dia) — B.5/D.4
#   auto_or_queue — autônoma até severidade alta, aí vai para fila do tutor — B.5
#   queue         — sempre exige aprovação do tutor — B.5
TOOLS = {
    "obter_perfil_resumido":      {"fn": obter_perfil_resumido,      "tier": "read"},
    "historico_intervencoes":     {"fn": historico_intervencoes,     "tier": "read"},
    "listar_competencias_fracas": {"fn": listar_competencias_fracas, "tier": "read"},
    "listar_recursos_remediacao": {"fn": listar_recursos_remediacao, "tier": "read"},
    "listar_questoes_reforco":    {"fn": listar_questoes_reforco,    "tier": "read"},
    "criar_intervencao":          {"fn": criar_intervencao,          "tier": "auto"},
    "criar_ova_personalizada":    {"fn": criar_ova_personalizada,    "tier": "auto"},
    "agendar_revisao":            {"fn": agendar_revisao,            "tier": "auto"},
    "ajustar_dificuldade":        {"fn": ajustar_dificuldade,        "tier": "auto_capped"},
    "alertar_tutor":              {"fn": alertar_tutor,              "tier": "auto_or_queue"},
    "propor_mensagem_do_tutor":   {"fn": propor_mensagem_do_tutor,   "tier": "queue"},
}


def tier_of(name):
    """Tier de autonomia de uma tool (default 'read' se desconhecida)."""
    return (TOOLS.get(name) or {}).get("tier", "read")


# JSON-schemas das tools novas (as 4 originais já estão em TOOLS_SCHEMA).
_EXTRA_SCHEMA = {
    "obter_perfil_resumido": {
        "name": "obter_perfil_resumido",
        "description": ("Retorna um resumo do estado do aluno (dias sem acesso, "
                        "consumo, taxa de erro no quiz, competência mais fraca). "
                        "Use para perceber a situação antes de agir."),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "historico_intervencoes": {
        "name": "historico_intervencoes",
        "description": ("Histórico recente das intervenções do agente para o aluno "
                        "COM o resultado (aceita/dispensada/melhorou/expirada). Use "
                        "para NÃO repetir uma abordagem que já foi dispensada."),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "criar_intervencao": {
        "name": "criar_intervencao",
        "description": ("Cria uma intervenção (mensagem proativa) para o aluno. "
                        "Idempotente por (aluno, tipo, dia). Use uma vez, ao decidir "
                        "falar com o aluno."),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "description": "Rótulo curto (ex.: plano_retomada)."},
                "mensagem_aluno": {"type": "string", "description": "Texto dirigido ao aluno."},
                "prioridade": {"type": "string", "enum": ["alta", "media", "baixa"]},
            },
            "required": ["tipo", "mensagem_aluno"],
        },
    },
    "agendar_revisao": {
        "name": "agendar_revisao",
        "description": ("Agenda a revisão espaçada de uma competência do curso do "
                        "aluno, a N dias. Idempotente."),
        "input_schema": {
            "type": "object",
            "properties": {
                "competency_id": {"type": "integer"},
                "days_from_now": {"type": "integer", "description": "Dias até a revisão (default 3)."},
            },
            "required": ["competency_id"],
        },
    },
    "ajustar_dificuldade": {
        "name": "ajustar_dificuldade",
        "description": ("Ajusta em ±1 o nível de dificuldade do quiz do aluno numa "
                        "competência (máx. 1 vez/dia). Sobe quando o aluno domina; "
                        "desce quando erra muito."),
        "input_schema": {
            "type": "object",
            "properties": {
                "competency_id": {"type": "integer"},
                "delta": {"type": "integer", "enum": [-1, 1]},
            },
            "required": ["competency_id", "delta"],
        },
    },
    "alertar_tutor": {
        "name": "alertar_tutor",
        "description": ("Gera um alerta para o tutor. Severidade baixa/media vira "
                        "alerta direto; ALTA entra na fila de aprovação do tutor "
                        "(o aluno não é notificado até aprovar)."),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string"},
                "mensagem": {"type": "string"},
                "severidade": {"type": "string", "enum": ["alta", "media", "baixa"]},
            },
            "required": ["tipo", "mensagem", "severidade"],
        },
    },
    "propor_mensagem_do_tutor": {
        "name": "propor_mensagem_do_tutor",
        "description": ("Propõe uma mensagem que o TUTOR enviaria ao aluno. Entra "
                        "SEMPRE na fila de aprovação — nada é enviado ao aluno sem "
                        "o tutor aprovar."),
        "input_schema": {
            "type": "object",
            "properties": {
                "mensagem_aluno": {"type": "string"},
                "justificativa": {"type": "string"},
            },
            "required": ["mensagem_aluno"],
        },
    },
}

# Catálogo de schemas por nome (as 4 originais + as novas).
CATALOG_SCHEMA = {t["name"]: t for t in TOOLS_SCHEMA}
CATALOG_SCHEMA.update(_EXTRA_SCHEMA)


def schema_for(names):
    """Lista de schemas (formato Messages API) para um subconjunto do catálogo —
    cada fluxo do agente escolhe o seu toolset."""
    return [CATALOG_SCHEMA[n] for n in names if n in CATALOG_SCHEMA]


def execute_tool(name, tool_input, ctx):
    """Despacha a chamada de tool feita pelo modelo. Erros viram payload de
    erro (devolvido ao modelo como tool_result), nunca exceção que mata o loop."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Tool desconhecida: {name}"}
    try:
        return fn(ctx, **(tool_input or {}))
    except Exception as err:  # noqa: BLE001 — robustez do loop é proposital
        return {"error": f"Falha ao executar {name}: {err}"}
