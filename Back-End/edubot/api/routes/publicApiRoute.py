"""API pública de integração (`/api/v1/...`) — leitura por sistemas parceiros.

É a ÚNICA porta que um sistema externo deve atravessar. O acesso direto ao MySQL
(porta 3310) não deve ser aberto para ninguém de fora: entrega credencial de
banco, todas as linhas de todos os alunos e nenhuma trilha de quem leu o quê.
Aqui cada resposta passa por três filtros — chave válida, escopo casado e
pseudonimização por padrão — e cada requisição fica contabilizada na chave.

Todos os endpoints são GET e somente-leitura. Nada aqui escreve no banco além do
contador de uso da própria chave (ver api/apikey.py).

Convenções do contrato (estáveis — o `v1` do caminho é o compromisso):

  * Autenticação:  header `X-API-Key: ek_live_...`
  * Paginação:     `?limit=` (máx. 500) + `?after_id=` (cursor). A resposta traz
                   `next_after_id` quando há mais página, `null` no fim. Cursor e
                   não OFFSET porque a tabela de eventos cresce durante a
                   varredura e OFFSET pularia ou repetiria linhas.
  * Datas:         `?since=` / `?until=` em ISO-8601 (`2026-09-01` ou
                   `2026-09-01T14:30:00`).
  * Aluno:         identificado por `subject_id` (pseudônimo estável e opaco).
                   `student_id`, nome e RA só aparecem com o escopo
                   `students:pii`.
"""
import datetime
import json

from flask import Blueprint, g, request
from peewee import PeeweeException, fn, JOIN

from edubot.api.apikey import require_api_key, has_scope, pseudonym, SCOPES
from edubot.data.models.attempts import Attempts
from edubot.data.models.competencies import Competencies
from edubot.data.models.courses import Courses
from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.ova_section_progress import OVASectionProgress
from edubot.data.models.ovas import OVAs
from edubot.data.models.questions import Questions
from edubot.data.models.student_mastery import StudentMastery
from edubot.data.models.students import Students
from edubot.data.models.subjects import Subjects
from edubot.services.coverage import competency_coverage

app_public_api = Blueprint("public_api", __name__, url_prefix="/api/v1")

MAX_LIMIT = 500
DEFAULT_LIMIT = 100

# `context` dos eventos pode carregar texto livre escrito pelo aluno (pergunta ao
# tutor). O pipeline de gravação já minimiza isso sem consentimento
# (services/events._minimize_context); aqui aplicamos a segunda barreira: sem
# `students:pii`, a chave textual some do payload mesmo que tenha sido gravada.
_CONTEXT_TEXT_KEYS = ("text", "question", "prompt")


def _ok(payload):
    return json.dumps(payload, default=str, ensure_ascii=False), 200, \
        {"Content-Type": "application/json; charset=utf-8"}


def _bad_request(msg):
    return json.dumps({"error": msg, "status": 400}), 400, \
        {"Content-Type": "application/json; charset=utf-8"}


def _limit():
    """`?limit=` saneado. Valor fora da faixa é CLAMPADO, não rejeitado: um
    parceiro pedindo 10000 quer "o máximo", e devolver 400 aí só gera suporte."""
    try:
        return max(1, min(int(request.args.get("limit", DEFAULT_LIMIT)), MAX_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def _int_arg(name):
    try:
        raw = request.args.get(name)
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _date_arg(name):
    """Data ISO da query string. Retorna (valor, erro) — o chamador decide se um
    filtro malformado vira 400 (vira: silenciar levaria o parceiro a achar que
    está filtrando quando não está)."""
    raw = request.args.get(name)
    if not raw:
        return None, None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(raw, fmt), None
        except ValueError:
            continue
    return None, f"Parâmetro `{name}` inválido: use ISO-8601 (2026-09-01 ou 2026-09-01T14:30:00)."


def _subject(student_id):
    """Bloco de identificação do aluno. Pseudônimo sempre; identidade só com
    `students:pii`. Ponto único desta decisão — nenhum endpoint monta isso na mão."""
    out = {"subject_id": pseudonym(student_id)}
    if has_scope("students:pii"):
        out["student_id"] = student_id
    return out


def _clean_context(ctx):
    """Remove texto livre do contexto do evento quando a chave não tem PII."""
    if not isinstance(ctx, dict) or has_scope("students:pii"):
        return ctx
    if not any(k in ctx for k in _CONTEXT_TEXT_KEYS):
        return ctx
    return {k: (None if k in _CONTEXT_TEXT_KEYS else v) for k, v in ctx.items()}


def _paged(rows, id_field, limit):
    """Envelope de paginação. `next_after_id` é o id da ÚLTIMA linha desta página
    quando ela veio cheia — se veio parcial, acabou e o cursor é null."""
    return {
        "data": rows,
        "count": len(rows),
        "next_after_id": rows[-1][id_field] if len(rows) == limit else None,
    }


# ---------------------------------------------------------------------------
# Meta — o parceiro descobre sozinho o que a chave dele pode fazer.
# Exige chave válida, mas nenhum escopo: é a rota de "meu setup está certo?".
# ---------------------------------------------------------------------------
@app_public_api.route("/ping", methods=["GET"])
@require_api_key()
def ping():
    return _ok({
        "ok": True,
        "service": "EduBot Public API",
        "version": "v1",
        "server_time": datetime.datetime.now().isoformat(timespec="seconds"),
        "key_name": g.api_key.name,
        "scopes": g.api_key.scope_list(),
    })


@app_public_api.route("/scopes", methods=["GET"])
@require_api_key()
def list_scopes():
    """Catálogo de escopos + quais a chave tem. Evita a ida-e-volta por e-mail
    quando o parceiro toma 403 e não sabe o que pedir."""
    granted = g.api_key.scope_list()
    return _ok({"scopes": [{"scope": s, "descricao": d, "concedido": s in granted}
                           for s, d in SCOPES.items()]})


# ---------------------------------------------------------------------------
# Catálogo — conteúdo. Sem dado pessoal em nenhuma linha.
# ---------------------------------------------------------------------------
@app_public_api.route("/catalog/courses", methods=["GET"])
@require_api_key("catalog:read")
def catalog_courses():
    try:
        rows = list(Courses.select(Courses.course_id, Courses.course_name)
                    .order_by(Courses.course_id).dicts())
        return _ok({"data": rows, "count": len(rows)})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/catalog/ovas", methods=["GET"])
@require_api_key("catalog:read")
def catalog_ovas():
    """OVAs publicados. `?subject_id=` recorta por assunto."""
    try:
        query = (OVAs
                 .select(OVAs.ova_id, OVAs.ova_name, OVAs.ova_name_en,
                         OVAs.subject_id, OVAs.num_interactions, OVAs.link,
                         OVAs.quiz_gate_perc,
                         Subjects.subject_name.alias("subject_name"))
                 .join(Subjects, JOIN.LEFT_OUTER,
                       on=(OVAs.subject_id == Subjects.subject_id)))
        subject_id = _int_arg("subject_id")
        if subject_id is not None:
            query = query.where(OVAs.subject_id == subject_id)
        rows = list(query.order_by(OVAs.ova_id).dicts())
        return _ok({"data": rows, "count": len(rows)})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/catalog/competencies", methods=["GET"])
@require_api_key("catalog:read")
def catalog_competencies():
    try:
        rows = list(Competencies
                    .select(Competencies.competency_id,
                            Competencies.competency_description,
                            Competencies.competency_description_en,
                            Competencies.subject_id,
                            Subjects.subject_name.alias("subject_name"))
                    .join(Subjects, JOIN.LEFT_OUTER,
                          on=(Competencies.subject_id == Subjects.subject_id))
                    .order_by(Competencies.competency_id).dicts())
        return _ok({"data": rows, "count": len(rows)})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/catalog/questions", methods=["GET"])
@require_api_key("catalog:read")
def catalog_questions():
    """Banco de questões. `?ova_id=` / `?competency_id=` recortam.

    O GABARITO (`answer`) NÃO vem por padrão: o mesmo endpoint serve para um
    parceiro montar uma tela de estudo, e nesse caso a resposta correta no
    payload vaza para o navegador do aluno. Quem precisa corrigir pede
    `?include_answer=1` — decisão explícita de quem integra, registrada na query.
    """
    try:
        fields = [Questions.question_id, Questions.statement, Questions.statement_en,
                  Questions.alternatives, Questions.alternatives_en,
                  Questions.ova_id, Questions.competency_id, Questions.difficulty]
        include_answer = request.args.get("include_answer", "0").lower() in ("1", "true", "yes")
        if include_answer:
            fields.append(Questions.answer)
        query = Questions.select(*fields)
        ova_id = _int_arg("ova_id")
        if ova_id is not None:
            query = query.where(Questions.ova_id == ova_id)
        competency_id = _int_arg("competency_id")
        if competency_id is not None:
            query = query.where(Questions.competency_id == competency_id)
        rows = list(query.order_by(Questions.question_id).dicts())
        return _ok({"data": rows, "count": len(rows), "gabarito_incluido": include_answer})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


# ---------------------------------------------------------------------------
# Rastreio — o núcleo do trabalho de rastreabilidade, pseudonimizado.
# ---------------------------------------------------------------------------
@app_public_api.route("/tracking/events", methods=["GET"])
@require_api_key("tracking:read")
def tracking_events():
    """Eventos de aprendizado (xAPI-lite), do mais antigo ao mais novo.

    Filtros: `since`, `until`, `verb`, `object_type`, `subject_id`.
    Paginação por cursor: `after_id` + `limit`.

    A ordem é CRESCENTE por event_id de propósito: é o que torna o cursor um
    ponto de sincronização — o parceiro guarda o último `next_after_id` e na
    próxima rodada só recebe o que entrou depois."""
    try:
        since, err = _date_arg("since")
        if err:
            return _bad_request(err)
        until, err = _date_arg("until")
        if err:
            return _bad_request(err)

        limit = _limit()
        query = LearningEvents.select()
        after_id = _int_arg("after_id")
        if after_id is not None:
            query = query.where(LearningEvents.event_id > after_id)
        if since:
            query = query.where(LearningEvents.occurred_at >= since)
        if until:
            query = query.where(LearningEvents.occurred_at <= until)
        verb = request.args.get("verb")
        if verb:
            query = query.where(LearningEvents.verb == verb)
        object_type = request.args.get("object_type")
        if object_type:
            query = query.where(LearningEvents.object_type == object_type)

        # Filtro por aluno: o parceiro só conhece o pseudônimo, então resolvemos
        # o pseudônimo -> student_id do nosso lado. São poucos alunos; comparar o
        # hash de cada um é mais simples e seguro do que guardar um mapa reverso.
        wanted = request.args.get("subject_id")
        if wanted:
            ids = [s.student_id for s in Students.select(Students.student_id)
                   if pseudonym(s.student_id) == wanted]
            if not ids:
                return _ok({"data": [], "count": 0, "next_after_id": None})
            query = query.where(LearningEvents.student_id.in_(ids))

        rows = []
        for ev in query.order_by(LearningEvents.event_id.asc()).limit(limit):
            sid = ev.student_id.student_id if hasattr(ev.student_id, "student_id") else ev.student_id
            rows.append({
                "event_id": ev.event_id,
                **_subject(sid),
                "verb": ev.verb,
                "object_type": ev.object_type,
                "object_id": ev.object_id,
                "context": _clean_context(ev.context),
                "occurred_at": ev.occurred_at,
            })
        return _ok(_paged(rows, "event_id", limit))
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/tracking/progress", methods=["GET"])
@require_api_key("tracking:read")
def tracking_progress():
    """Progresso por (aluno, OVA): tempo de leitura, % percorrido, conclusão."""
    try:
        limit = _limit()
        query = OVAProgress.select()
        after_id = _int_arg("after_id")
        if after_id is not None:
            query = query.where(OVAProgress.progress_id > after_id)
        ova_id = _int_arg("ova_id")
        if ova_id is not None:
            query = query.where(OVAProgress.ova_id == ova_id)
        if request.args.get("completed") in ("1", "true", "yes"):
            query = query.where(OVAProgress.completed == True)

        rows = []
        for p in query.order_by(OVAProgress.progress_id.asc()).limit(limit):
            sid = p.student_id.student_id if hasattr(p.student_id, "student_id") else p.student_id
            oid = p.ova_id.ova_id if hasattr(p.ova_id, "ova_id") else p.ova_id
            rows.append({
                "progress_id": p.progress_id,
                **_subject(sid),
                "ova_id": oid,
                "read_time_seconds": p.read_time,
                "perc_scrolled": p.perc_scrolled,
                "completed": bool(p.completed),
                "last_access": p.last_access,
            })
        return _ok(_paged(rows, "progress_id", limit))
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/tracking/sections", methods=["GET"])
@require_api_key("tracking:read")
def tracking_sections():
    """Leitura por SEÇÃO do OVA — onde o aluno gastou tempo e o que releu.

    É o dado mais fino do rastreio (`visits > 1` = releitura) e o que responde
    "onde ele travou", que o progresso agregado do OVA não responde."""
    try:
        limit = _limit()
        query = OVASectionProgress.select()
        after_id = _int_arg("after_id")
        if after_id is not None:
            query = query.where(OVASectionProgress.section_progress_id > after_id)
        ova_id = _int_arg("ova_id")
        if ova_id is not None:
            query = query.where(OVASectionProgress.ova_id == ova_id)

        rows = []
        for s in query.order_by(OVASectionProgress.section_progress_id.asc()).limit(limit):
            sid = s.student_id.student_id if hasattr(s.student_id, "student_id") else s.student_id
            oid = s.ova_id.ova_id if hasattr(s.ova_id, "ova_id") else s.ova_id
            rows.append({
                "section_progress_id": s.section_progress_id,
                **_subject(sid),
                "ova_id": oid,
                "section_id": s.section_id,
                "section_index": s.section_index,
                "active_seconds": s.active_seconds,
                "max_scroll_perc": s.max_scroll_perc,
                "visits": s.visits,
                "last_access": s.last_access,
            })
        return _ok(_paged(rows, "section_progress_id", limit))
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


# ---------------------------------------------------------------------------
# Métricas agregadas — nenhuma linha identifica indivíduo, por construção.
# ---------------------------------------------------------------------------
@app_public_api.route("/metrics/mastery", methods=["GET"])
@require_api_key("metrics:read")
def metrics_mastery():
    """Domínio médio por competência na turma (BKT) + tamanho da amostra.

    `alunos` vem junto de propósito: uma média de domínio sobre 2 alunos não
    significa o mesmo que sobre 200, e sem o N quem consome não tem como saber."""
    try:
        rows = list(StudentMastery
                    .select(StudentMastery.competency_id.alias("competency_id"),
                            fn.AVG(StudentMastery.p_mastery).alias("dominio_medio"),
                            fn.COUNT(StudentMastery.student_id).alias("alunos"),
                            fn.SUM(StudentMastery.attempts_seen).alias("tentativas"))
                    .group_by(StudentMastery.competency_id)
                    .dicts())
        nomes = {c.competency_id: c.competency_description
                 for c in Competencies.select(Competencies.competency_id,
                                              Competencies.competency_description)}
        out = [{
            "competency_id": r["competency_id"],
            "competencia": nomes.get(r["competency_id"]),
            "dominio_medio": round(float(r["dominio_medio"] or 0), 4),
            "alunos": r["alunos"],
            "tentativas": int(r["tentativas"] or 0),
        } for r in rows]
        out.sort(key=lambda x: x["dominio_medio"])
        return _ok({"data": out, "count": len(out)})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/metrics/questions", methods=["GET"])
@require_api_key("metrics:read")
def metrics_questions():
    """Taxa de acerto por questão — o item-analysis do banco de questões."""
    try:
        rows = list(Attempts
                    .select(Attempts.question_id.alias("question_id"),
                            fn.COUNT(Attempts.attempt_id).alias("tentativas"),
                            fn.SUM(Attempts.is_correct).alias("acertos"))
                    .group_by(Attempts.question_id)
                    .dicts())
        out = []
        for r in rows:
            total = r["tentativas"] or 0
            acertos = int(r["acertos"] or 0)
            out.append({
                "question_id": r["question_id"],
                "tentativas": total,
                "acertos": acertos,
                "taxa_acerto": round(acertos / total, 4) if total else None,
            })
        out.sort(key=lambda x: (x["taxa_acerto"] is None, x["taxa_acerto"]))
        return _ok({"data": out, "count": len(out)})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/metrics/coverage", methods=["GET"])
@require_api_key("metrics:read")
def metrics_coverage():
    """Cobertura de conteúdo por competência (`?course_id=` recorta).

    Reusa services/coverage.py — a regra do que é "remediável" mora lá e não é
    reimplementada aqui."""
    try:
        return _ok({"data": competency_coverage(_int_arg("course_id"))})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


@app_public_api.route("/metrics/engagement", methods=["GET"])
@require_api_key("metrics:read")
def metrics_engagement():
    """Volume de eventos por verbo na janela (`?since=` / `?until=`) — o pulso de
    uso da plataforma, sem tocar em indivíduo."""
    try:
        since, err = _date_arg("since")
        if err:
            return _bad_request(err)
        until, err = _date_arg("until")
        if err:
            return _bad_request(err)
        query = (LearningEvents
                 .select(LearningEvents.verb.alias("verb"),
                         fn.COUNT(LearningEvents.event_id).alias("eventos"),
                         fn.COUNT(fn.DISTINCT(LearningEvents.student_id)).alias("alunos")))
        if since:
            query = query.where(LearningEvents.occurred_at >= since)
        if until:
            query = query.where(LearningEvents.occurred_at <= until)
        rows = list(query.group_by(LearningEvents.verb).dicts())
        rows.sort(key=lambda r: -r["eventos"])
        return _ok({"data": rows, "count": len(rows)})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500


# ---------------------------------------------------------------------------
# Alunos — pseudonimizado por padrão; nome/RA só com `students:pii`.
# ---------------------------------------------------------------------------
@app_public_api.route("/students", methods=["GET"])
@require_api_key("students:read")
def students_list():
    """Alunos. `?course_id=` recorta.

    Sem `students:pii` a resposta traz só o pseudônimo, o curso e o papel — o
    suficiente para o parceiro montar coortes e cruzar com os eventos, sem
    identificar ninguém. Com `students:pii`, acrescenta student_id, nome e RA.
    `student_password` não é selecionado em hipótese alguma."""
    try:
        fields = [Students.student_id, Students.course_id, Students.role,
                  Students.is_admin, Students.persona, Students.nickname]
        pii = has_scope("students:pii")
        if pii:
            fields += [Students.student_name, Students.ra]
        query = Students.select(*fields)
        course_id = _int_arg("course_id")
        if course_id is not None:
            query = query.where(Students.course_id == course_id)

        rows = []
        for s in query.order_by(Students.student_id).limit(_limit()):
            row = {
                **_subject(s.student_id),
                "course_id": s.course_id.course_id if hasattr(s.course_id, "course_id") else s.course_id,
                "role": s.role,
                "is_admin": bool(s.is_admin),
                "persona": s.persona,
                "nickname": s.nickname,
            }
            if pii:
                row["student_name"] = s.student_name
                row["ra"] = s.ra
            rows.append(row)
        return _ok({"data": rows, "count": len(rows), "pii_incluido": pii})
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500
