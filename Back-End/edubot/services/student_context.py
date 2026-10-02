# MELHORIA (4.2) — Contexto completo do aluno.
#
# Monta, a partir do banco, o perfil completo do aluno logado:
#   - quais recursos ele já consumiu (por OVA e por tipo de mídia)
#   - histórico de desempenho por competência
#   - dias de inatividade, taxa de erro em quizzes, atividades pendentes
#   - formato de conteúdo preferido (vídeo / texto / podcast)
#
# Este dicionário é a ÚNICA entrada do edubot_agent (4.3) e também alimenta o
# painel de rastreamento (4.4) via GET /student/me. Centralizar a montagem aqui
# evita que cada rota re-derive as mesmas métricas de formas divergentes.
#
# A.1 (Plano de Execução — Etapa 1): a montagem foi reescrita de loops N+1
# (dezenas de queries por competência × recurso) para AGREGAÇÕES SQL. O perfil
# passou de ~30 queries para 8. O contrato do dict de saída é idêntico
# (garantido por tests/test_profile_contract.py); só o caminho até ele mudou.
import datetime
import os

from peewee import Case, JOIN, fn

from edubot.i18n import tr

from edubot.data.models.students import Students
from edubot.data.models.courses import Courses
from edubot.data.models.ovas import OVAs
from edubot.data.models.interactions import Interactions
from edubot.data.models.questions import Questions
from edubot.data.models.answers import Answers
from edubot.data.models.attempts import Attempts
from edubot.data.models.competencies import Competencies
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.resources import Resources
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.interventions import Interventions
from edubot.data.models.offerings import Offerings
from edubot.data.models.subjects import Subjects
from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.student_mastery import StudentMastery
from edubot.services.mastery import status_from_mastery as mastery_status

# Thresholds (kept in one place so the pedagogy team can tune them)
COMPETENCY_DEVELOPED_RATIO = 0.8   # >= 80% of the competency questions correct
MEDIA_COMPLETED_PERC = 90          # video/podcast considered concluded at >= 90%
TEXT_CONSUMED_PERC = 80            # texto considered consumed at >= 80% scrolled


def _as_date(value):
    """Normaliza um valor de data/hora (date, datetime ou string do SQLite)
    para datetime.date, ou None."""
    if not value:
        return None
    if isinstance(value, str):  # SQLite devolve strings em agregações
        value = value.replace("/", "-")
        try:
            return datetime.date.fromisoformat(value[:10])
        except ValueError:
            return None
    if isinstance(value, datetime.datetime):
        return value.date()
    return value  # já é datetime.date


def _student_id(student):
    return student.student_id if hasattr(student, "student_id") else student


def _days_without_access(student):
    """Dias desde a última atividade do aluno (A2).

    Considera TODO sinal de estudo (interações, leitura de OVA, consumo de mídia
    e tentativas de quiz), não só `interactions` — um aluno que lê, assiste vídeo
    e responde quiz todo dia sem tocar num carrossel não aparece mais como
    inativo. A.1: os quatro MAX viram uma única query (UNION ALL), o que também
    baixa o custo do painel do tutor, que chama esta função por aluno."""
    sid = _student_id(student)
    parts = [
        Interactions.select(fn.MAX(Interactions.interaction_date))
                    .where(Interactions.student_id == sid),
        OVAProgress.select(fn.MAX(OVAProgress.last_access))
                   .where(OVAProgress.student_id == sid),
        ResourceProgress.select(fn.MAX(ResourceProgress.last_access))
                        .where(ResourceProgress.student_id == sid),
        Attempts.select(fn.MAX(Attempts.attempt_time))
                .where(Attempts.student_id == sid),
        # D.1: 5ª fonte — qualquer evento de aprendizado (login, mídia, tutor)
        # também conta como atividade, inclusive os que não geram Attempt nem
        # progresso (ex.: um aluno que só assistiu vídeo e perguntou ao tutor).
        LearningEvents.select(fn.MAX(LearningEvents.occurred_at))
                      .where(LearningEvents.student_id == sid),
    ]
    union = parts[0]
    for part in parts[1:]:
        union = union.union_all(part)

    dates = [d for d in (_as_date(row[0]) for row in union.tuples()) if d is not None]
    if not dates:
        return None
    return (datetime.date.today() - max(dates)).days


def _competency_rows(student, course_id, lang="pt"):
    """Status por competência do curso do aluno, em UMA query agregada.

    Antes eram 4 counts por competência num loop (N+1). Agora: JOIN de
    Competencies → Questions → (Answers do aluno) → (Attempts do aluno) com
    GROUP BY. COUNT(DISTINCT ...) neutraliza o fan-out do join; `answers` é ≤1
    por (aluno, questão) — unique uc_answers — então o SUM de erros não duplica.

    É esse erro POR competência (e não a taxa global) que o agente usa para
    decidir QUAL assunto remediar com uma OVA personalizada."""
    total_q = fn.COUNT(Questions.question_id.distinct()).alias("total_questoes")
    acertos = fn.COUNT(Answers.answer_id.distinct()).alias("acertos")
    tentativas = fn.COUNT(Attempts.attempt_id.distinct()).alias("tentativas")
    erros = fn.SUM(Case(None, [(Attempts.is_correct == False, 1)], 0)).alias("erros")
    # D.2: p_mastery vem do LEFT JOIN com student_mastery. É ≤1 linha por
    # (aluno, competência); MAX evita conflito com ONLY_FULL_GROUP_BY do MySQL.
    p_mastery = fn.MAX(StudentMastery.p_mastery).alias("p_mastery")
    # Plano 5 (17.1): assunto (disciplina) da competência. O JOIN com Subjects já
    # existe (para o filtro por curso); só faltava expor o vínculo. subject_id é
    # funcionalmente dependente da competência (1 assunto por competência), então
    # MAX é seguro/determinístico e satisfaz o ONLY_FULL_GROUP_BY do MySQL.
    subject_id = fn.MAX(Subjects.subject_id).alias("subject_id")
    subject_nome = fn.MAX(Subjects.subject_name).alias("subject_nome")

    sid = _student_id(student)
    rows = (Competencies
            .select(Competencies.competency_id,
                    Competencies.competency_description,
                    Competencies.competency_description_en,
                    total_q, acertos, tentativas, erros, p_mastery,
                    subject_id, subject_nome)
            .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id))
            .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
            .switch(Competencies)
            .join(Questions, JOIN.LEFT_OUTER,
                  on=(Questions.competency_id == Competencies.competency_id))
            .join(Answers, JOIN.LEFT_OUTER,
                  on=((Answers.question_id == Questions.question_id) &
                      (Answers.student_id == sid)))
            .switch(Questions)
            .join(Attempts, JOIN.LEFT_OUTER,
                  on=((Attempts.question_id == Questions.question_id) &
                      (Attempts.student_id == sid)))
            .switch(Competencies)
            .join(StudentMastery, JOIN.LEFT_OUTER,
                  on=((StudentMastery.competency_id == Competencies.competency_id) &
                      (StudentMastery.student_id == sid)))
            .where(Offerings.course_id == course_id)
            .group_by(Competencies.competency_id)
            .order_by(Competencies.competency_id)
            .dicts())

    statuses = []
    for row in rows:
        total = row["total_questoes"] or 0
        correct = row["acertos"] or 0
        attempts_total = row["tentativas"] or 0
        attempts_wrong = int(row["erros"] or 0)
        taxa_erro = round(attempts_wrong / attempts_total, 2) if attempts_total else None

        # D.2: o status passa a derivar de p_mastery (sinal contínuo, com tempo e
        # esquecimento). DEGRADAÇÃO SEGURA: onde ainda não há linha de mastery
        # (backfill não rodado, ou competência nunca tentada), cai na razão
        # acertos/total antiga — o perfil nunca fica sem status.
        pm = row.get("p_mastery")
        dominio_estimado = round(pm, 2) if pm is not None else None
        if pm is not None:
            status = mastery_status(pm)
        else:
            ratio = (correct / total) if total else 0
            if total == 0 or correct == 0:
                status = "não iniciada"
            elif ratio >= COMPETENCY_DEVELOPED_RATIO:
                status = "desenvolvida"
            else:
                status = "em desenvolvimento"
        statuses.append({
            "competency_id": row["competency_id"],
            "nome": tr(row["competency_description"],
                       row["competency_description_en"], lang),
            # Plano 5 (17.1): assunto/disciplina — permite agrupar acertos/erros
            # "por assunto" no front (aluno, professor e gestor). subject_name é PT
            # (course_subjects não tem coluna _en); o nome vai direto, sem tr().
            "subject_id": row.get("subject_id"),
            "subject_nome": row.get("subject_nome"),
            "acertos": correct,
            "total_questoes": total,
            "status": status,
            "tentativas": attempts_total,
            "erros": attempts_wrong,
            "taxa_erro": taxa_erro,
            # D.2: domínio estimado (0..1) — o front mostra "domínio: 74%".
            # None quando ainda não há sinal de mastery para a competência.
            "dominio_estimado": dominio_estimado
        })
    return statuses


def _resource_state(res_row, ova_prog, has_quiz_attempt, lang="pt"):
    """Consumo de um recurso, a partir de linhas JÁ carregadas (sem query).

    res_row: dict do JOIN Resources × ResourceProgress (do aluno).
    ova_prog: dict {exists, read_time, perc_scrolled} do OVA do recurso (texto).
    has_quiz_attempt: bool — o aluno tem alguma tentativa no OVA (quiz)."""
    rtype = res_row["resource_type"]
    consumed = False
    perc = 0
    seconds = 0
    completed = False

    if rtype in ("video", "podcast", "atividade"):
        if res_row["rp_exists"]:
            perc = res_row["rp_perc"] or 0
            seconds = res_row["rp_seconds"] or 0
            completed = bool(res_row["rp_completed"]) or perc >= MEDIA_COMPLETED_PERC
            consumed = completed or perc > 0 or seconds > 0
    elif rtype == "texto":
        # Texto vive na própria página do OVA: consumo = leitura/scroll
        if ova_prog and ova_prog["exists"]:
            perc = ova_prog["perc_scrolled"] or 0
            seconds = ova_prog["read_time"] or 0
            completed = perc >= TEXT_CONSUMED_PERC
            consumed = perc > 0 or seconds > 0
    elif rtype == "quiz":
        consumed = has_quiz_attempt
        completed = has_quiz_attempt

    return {
        "resource_id": res_row["resource_id"],
        "titulo": tr(res_row["resource_title"], res_row["resource_title_en"], lang),
        "tipo": rtype,
        "url": res_row["resource_url"],
        "media_type": res_row["media_type"],
        "perc_consumido": perc,
        "segundos_consumidos": seconds,
        "consumido": consumed,
        "concluido": completed
    }


def build_student_profile(student, lang="pt"):
    """Builds the full profile dict for a Students row (the agent's input).

    `lang` (Fase 4 — A12): nomes de OVA, títulos de recursos e competências são
    servidos no idioma pedido (fallback PT). Métricas independem do idioma.

    A.1: montado em 8 queries agregadas (course, dias, ovas+progresso,
    recursos+progresso, has-quiz por OVA, competências, totais de quiz,
    histórico) — o contrato do dict é idêntico ao da versão N+1."""
    sid = _student_id(student)
    # `course_id` é uma ForeignKeyField: acessar `student.course_id` já faz o
    # lazy-load do objeto Courses (1 query, cacheada na instância). Reusamos esse
    # objeto como `course` — evita um SELECT extra em `courses` (o antigo
    # Courses.get_or_none duplicava o lazy-load). O id inteiro alimenta os filtros
    # sem re-disparar a FK.
    course = student.course_id
    course_id = course.course_id if course else None

    # --- OVAs do curso + progresso do aluno (1 query, LEFT JOIN) -------------
    ova_rows = (OVAs
                .select(OVAs.ova_id, OVAs.ova_name, OVAs.ova_name_en, OVAs.link,
                        OVAProgress.progress_id.alias("progress_id"),
                        OVAProgress.read_time.alias("read_time"),
                        OVAProgress.perc_scrolled.alias("perc_scrolled"),
                        OVAProgress.completed.alias("completed"),
                        OVAProgress.last_access.alias("last_access"))
                .join(Subjects, on=(OVAs.subject_id == Subjects.subject_id))
                .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
                .switch(OVAs)
                .join(OVAProgress, JOIN.LEFT_OUTER,
                      on=((OVAProgress.ova_id == OVAs.ova_id) &
                          (OVAProgress.student_id == sid)))
                .where(Offerings.course_id == course_id)
                .order_by(OVAs.ova_id)
                .dicts())
    ova_rows = list(ova_rows)

    # progresso por ova_id (para os recursos do tipo "texto")
    ova_prog = {}
    for r in ova_rows:
        has = r["progress_id"] is not None
        ova_prog[r["ova_id"]] = {
            "exists": has,
            "read_time": r["read_time"] if has else 0,
            "perc_scrolled": r["perc_scrolled"] if has else 0,
        }

    # --- Recursos do curso + progresso do aluno (1 query, LEFT JOIN) --------
    res_rows = (Resources
                .select(Resources.resource_id, Resources.ova_id,
                        Resources.resource_type, Resources.resource_title,
                        Resources.resource_title_en, Resources.resource_url,
                        Resources.media_type,
                        ResourceProgress.resource_progress_id.alias("rp_id"),
                        ResourceProgress.perc_consumed.alias("rp_perc"),
                        ResourceProgress.seconds_consumed.alias("rp_seconds"),
                        ResourceProgress.completed.alias("rp_completed"))
                .join(OVAs, on=(Resources.ova_id == OVAs.ova_id))
                .join(Subjects, on=(OVAs.subject_id == Subjects.subject_id))
                .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
                .switch(Resources)
                .join(ResourceProgress, JOIN.LEFT_OUTER,
                      on=((ResourceProgress.resource_id == Resources.resource_id) &
                          (ResourceProgress.student_id == sid)))
                .where(Offerings.course_id == course_id)
                .order_by(Resources.ova_id, Resources.resource_id)
                .dicts())
    resources_by_ova = {}
    for r in res_rows:
        r["rp_exists"] = r["rp_id"] is not None
        resources_by_ova.setdefault(r["ova_id"], []).append(r)

    # --- OVAs com alguma tentativa de quiz do aluno (1 query) ---------------
    ova_ids_with_attempts = set(
        row[0] for row in (Attempts
                           .select(Questions.ova_id)
                           .join(Questions, on=(Attempts.question_id == Questions.question_id))
                           .where(Attempts.student_id == sid)
                           .distinct()
                           .tuples()))

    # --- Montagem por OVA ---------------------------------------------------
    ovas_data = []
    total_resources = 0
    consumed_resources = 0
    consumption_by_type = {}

    for ova in ova_rows:
        ova_id = ova["ova_id"]
        has_quiz_attempt = ova_id in ova_ids_with_attempts
        resources_data = []
        for res_row in resources_by_ova.get(ova_id, []):
            state = _resource_state(res_row, ova_prog.get(ova_id),
                                    has_quiz_attempt, lang)
            resources_data.append(state)
            total_resources += 1
            stats = consumption_by_type.setdefault(
                res_row["resource_type"], {"total": 0, "consumidos": 0, "concluidos": 0})
            stats["total"] += 1
            if state["consumido"]:
                consumed_resources += 1
                stats["consumidos"] += 1
            if state["concluido"]:
                stats["concluidos"] += 1

        prog = ova_prog[ova_id]
        ovas_data.append({
            "ova_id": ova_id,
            "ova_name": tr(ova["ova_name"], ova["ova_name_en"], lang),
            # link da página HTML do OVA — usado pelo frontend React para abrir
            # o leitor clássico (iframe.html) com o conteúdo de texto
            "link": ova["link"],
            "read_time": ova["read_time"] if prog["exists"] else 0,
            "perc_scrolled": ova["perc_scrolled"] if prog["exists"] else 0,
            "completed": bool(ova["completed"]) if prog["exists"] else False,
            # U.4: timestamp da última atividade neste OVA — o front usa o maior
            # para o card "continuar de onde parou". None quando nunca acessado.
            "last_access": str(ova["last_access"]) if prog["exists"] and ova["last_access"] else None,
            "recursos": resources_data
        })

    perc_consumed = round(100 * consumed_resources / total_resources) if total_resources else 0

    # --- preferred format (P.1 v2: por CONCLUSÃO, não por consumo) -----------
    # Antes: o formato mais CONSUMIDO. Agora: o formato que o aluno mais CONCLUI
    # (concluidos), sinal mais forte de que aprende melhor ali (começar um vídeo
    # != aprender com ele). Mesma query — só muda a métrica de desempate. O
    # serviço preferences.learning_preference (P.1) refina isso com a taxa de
    # conclusão e a resposta às intervenções; aqui fica a leitura barata do perfil.
    preferencia = None
    best = 0
    for rtype in ("video", "podcast", "texto"):
        stats = consumption_by_type.get(rtype)
        if stats and stats["concluidos"] > best:
            best = stats["concluidos"]
            preferencia = rtype

    # --- quiz performance (1 query agregada) --------------------------------
    quiz_row = (Attempts
                .select(fn.COUNT(Attempts.attempt_id).alias("total"),
                        fn.SUM(Case(None, [(Attempts.is_correct == False, 1)], 0)).alias("wrong"))
                .where(Attempts.student_id == sid)
                .dicts()
                .get())
    attempts_total = quiz_row["total"] or 0
    attempts_wrong = int(quiz_row["wrong"] or 0)
    quiz_error_rate = round(attempts_wrong / attempts_total, 2) if attempts_total else None

    # --- pending activities: accessed the OVA but didn't conclude it ---------
    # derivado das linhas já carregadas (sem query nova): OVA com progresso e
    # não concluído.
    pendentes = sum(1 for ova in ova_rows
                    if ova["progress_id"] is not None and not bool(ova["completed"]))

    # --- intervention/recommendation history (1 query) ----------------------
    historico = []
    for it in (Interventions
               .select()
               .where(Interventions.student_id == sid)
               .order_by(Interventions.date.desc())
               .limit(10)):
        historico.append({
            "data": str(it.date),
            "tipo": it.type,
            "descricao": it.description,
            "resultado": it.result
        })

    return {
        "estudante": {
            "student_id": student.student_id,
            "nome": student.student_name,
            "ra": student.ra,
            "curso": course.course_name if course else None,
            # MELHORIA (Cena 4): papel do usuário, para o frontend liberar o painel
            "role": getattr(student, "role", "aluno") or "aluno",
            # AV.2 (Plano 3): persona do companheiro (a linha do aluno já está
            # carregada — 0 query nova, contrato de 8 queries do perfil intacto).
            "persona": getattr(student, "persona", "edubot") or "edubot"
        },
        # CP.1 (Plano 3): flags de feature lidas do ambiente (0 query). `companion`
        # desligado = o leitor de OVA não monta o companheiro (idêntico ao atual).
        "features": {
            "companion": os.getenv("EDUBOT_COMPANION", "on").lower() in ("1", "true", "on", "yes"),
        },
        "dias_sem_acesso": _days_without_access(student),
        "recursos": {
            "total": total_resources,
            "consumidos": consumed_resources,
            "percentual_consumido": perc_consumed,
            "por_tipo": consumption_by_type
        },
        "preferencia_formato": preferencia,
        "quiz": {
            "tentativas": attempts_total,
            "erros": attempts_wrong,
            "taxa_erro": quiz_error_rate
        },
        "atividades_pendentes": pendentes,
        "ovas": ovas_data,
        "competencias": _competency_rows(student, course_id, lang),
        "historico_intervencoes": historico
    }
