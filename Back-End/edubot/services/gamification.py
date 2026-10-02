"""Gamificação núcleo (Plano 2 — Etapa 8): XP, nível, sequência, conquistas, ranking.

Princípios (não negociáveis):
  1. XP mede ESFORÇO, não talento — concluir, revisar EM DIA, voltar amanhã.
     Nota/domínio nunca entra no XP do ranking; dominar competência vira
     CONQUISTA pessoal (invisível aos colegas).
  2. Anti-farm por construção — XP só server-side; dedup por (aluno, regra,
     objeto, dia); teto diário por regra. Nada de XP por evento bruto do front.
  3. Perder a sequência ZERA o contador, nunca tira XP ganho; 1 escudo/semana.
  4. Tudo atrás da flag EDUBOT_GAMIFICATION (off -> award/register viram no-op e
     as rotas devolvem shape "desligado"; a plataforma fica idêntica à atual).

Este módulo NÃO tem rota própria; é chamado pelos ganchos (answer, progresso,
tutor-chat, /events, reviews) e pelas rotas de gamificação. Tudo best-effort:
uma falha aqui nunca quebra a requisição principal.
"""
import datetime
import logging
import os

from peewee import IntegrityError, fn

from edubot.data.models.student_achievements import StudentAchievements
from edubot.data.models.student_streak import StudentStreak
from edubot.data.models.students import Students
from edubot.data.models.xp_events import XpEvents

logger = logging.getLogger("edubot.gamification")

# --- Regras de XP: rule -> (pontos, teto_diario). teto_diario=0 => sem teto além
# do dedup por (aluno, regra, objeto, dia). ---------------------------------
XP_RULES = {
    "modulo_concluido":  (40, 0),   # transição de conclusão do OVA (D.1 completed)
    "quiz_do_modulo":    (15, 0),   # respondeu TODAS as questões do quiz (independe da nota!)
    "revisao_em_dia":    (30, 0),   # respondeu a revisão na data (D.3) — 1x/competência/dia
    "dia_de_estudo":     (10, 1),   # 1º sinal de estudo do dia (alimenta a sequência)
    "pergunta_ao_tutor": (5, 2),    # perguntar é esforço; teto 2/dia (anti-spam)
    "meta_semanal":      (50, 0),   # Etapa 9 (E.3)
    "desafio_tentado":   (20, 0),   # Etapa 9 (R.3) — por TENTAR, não por acertar
}

LEVEL_BASE = int(os.getenv("EDUBOT_XP_LEVEL_BASE", "60"))

# AV.1 (Plano 3) — a decisão R.1 do Plano 2 (personas desbloqueadas por NÍVEL) foi
# REVOGADA: personas são ferramenta de estudo, não recompensa, e ficam LIVRES para
# todos desde o 1º acesso. O catálogo é a única fonte; o desbloqueio some.
PERSONA_IDS = ["einstein", "curie"]

# R.2 (Plano 2) — títulos concedidos por conquista (id -> rótulo pt/en). O aluno
# escolhe o título ativo entre os que ganhou (students.title).
TITLE_BY_ACHIEVEMENT = {
    "revisor_pontual": ("Revisor Pontual", "On-time Reviewer"),
    "mestre_competencia": ("Mestre", "Master"),
    "sequencia_7": ("Consistente", "Consistent"),
    "trilha_completa": ("Trilha Completa", "Track Finisher"),
    "curioso": ("Curioso", "Curious Mind"),
}


def gamification_enabled():
    return os.getenv("EDUBOT_GAMIFICATION", "on").lower() in ("1", "true", "on", "yes")


# ---------------------------------------------------------------------------
# XP
# ---------------------------------------------------------------------------
def award(student_id, rule, object_type=None, object_id=None, today=None):
    """Concede XP da `rule` ao aluno. Idempotente e anti-farm. Best-effort.
    Retorna os pontos concedidos (0 se desligado, dedup, teto atingido ou falha)."""
    if not gamification_enabled():
        return 0
    spec = XP_RULES.get(rule)
    if not spec:
        return 0
    points, daily_cap = spec
    if points <= 0:
        return 0
    today = today or datetime.date.today()
    sid = getattr(student_id, "student_id", student_id)
    try:
        day_q = (XpEvents
                 .select()
                 .where((XpEvents.student_id == sid) & (XpEvents.rule == rule) &
                        (XpEvents.awarded_on == today)))
        # teto diário por regra (soma do dia, independe do objeto)
        if daily_cap > 0 and day_q.count() >= daily_cap:
            return 0
        if object_id is not None:
            # dedup do MESMO objeto no MESMO dia (a unique é o backstop de corrida)
            dup = day_q.where((XpEvents.object_type == object_type) &
                              (XpEvents.object_id == object_id)).exists()
            if dup:
                return 0
        elif daily_cap == 0:
            # regra sem objeto e sem teto: 1x/dia (NULLs não são únicos no SQL)
            if day_q.exists():
                return 0
        try:
            XpEvents.create(student_id=sid, rule=rule, object_type=object_type,
                            object_id=object_id, points=points, awarded_on=today,
                            created_at=datetime.datetime.now())
        except IntegrityError:
            return 0   # corrida: mesmo (aluno, regra, objeto, dia)
        return points
    except Exception:
        logger.exception("Falha ao conceder XP (%s) ao aluno %s", rule, sid)
        return 0


def xp_total(student_id):
    # int(): o SUM do MySQL volta Decimal (no SQLite dos testes, int) — normaliza
    # para evitar `Decimal ** float` no cálculo de nível.
    return int((XpEvents
                .select(fn.COALESCE(fn.SUM(XpEvents.points), 0))
                .where(XpEvents.student_id == student_id)
                .scalar()) or 0)


def xp_week(student_id, week_start=None):
    week_start = week_start or _week_start()
    week_end = week_start + datetime.timedelta(days=6)
    return int((XpEvents
                .select(fn.COALESCE(fn.SUM(XpEvents.points), 0))
                .where((XpEvents.student_id == student_id) &
                       (XpEvents.awarded_on >= week_start) &
                       (XpEvents.awarded_on <= week_end))
                .scalar()) or 0)


def level_from_xp(total):
    """Nível pela curva suave level = 1 + floor(sqrt(xp / base))."""
    return 1 + int((max(0.0, float(total)) / LEVEL_BASE) ** 0.5)


def xp_for_level(level):
    """XP mínimo para atingir `level` (inverso de level_from_xp)."""
    return LEVEL_BASE * (level - 1) ** 2


def level_progress(total):
    """Progresso dentro do nível atual (para a barra de XP)."""
    level = level_from_xp(total)
    floor_xp = xp_for_level(level)
    next_xp = xp_for_level(level + 1)
    return {
        "level": level,
        "xp_total": total,
        "into_level": total - floor_xp,
        "level_span": next_xp - floor_xp,
        "next_level_at": next_xp,
    }


# ---------------------------------------------------------------------------
# Sequência (streak) com escudo semanal
# ---------------------------------------------------------------------------
def _week_start(day=None):
    day = day or datetime.date.today()
    return day - datetime.timedelta(days=day.weekday())   # segunda-feira ISO


def _same_iso_week(a, b):
    return a is not None and b is not None and a.isocalendar()[:2] == b.isocalendar()[:2]


def update_streak(student_id, today=None):
    """Atualiza a sequência no 1º sinal de estudo do dia. Idempotente por dia.
    O escudo (1/semana) cobre exatamente 1 dia perdido. Retorna current_days."""
    today = today or datetime.date.today()
    sid = getattr(student_id, "student_id", student_id)
    row = StudentStreak.get_or_none(StudentStreak.student_id == sid)
    if row is None:
        StudentStreak.create(student_id=sid, current_days=1, best_days=1,
                             last_activity_date=today, shield_used_on=None)
        return 1
    last = row.last_activity_date
    if last == today:
        return row.current_days                      # já contado hoje
    if last == today - datetime.timedelta(days=1):
        row.current_days += 1                        # dia seguinte: cresce
    else:
        gap = (today - last).days if last else None
        shield_available = row.shield_used_on is None or not _same_iso_week(row.shield_used_on, today)
        if gap == 2 and shield_available:
            # exatamente 1 dia perdido e o escudo da semana está disponível
            row.shield_used_on = today
            row.current_days += 1
        else:
            row.current_days = 1                      # sequência quebrou -> zera (sem punição de XP)
    row.best_days = max(row.best_days or 0, row.current_days)
    row.last_activity_date = today
    row.save()
    return row.current_days


def streak_state(student_id, today=None):
    today = today or datetime.date.today()
    row = StudentStreak.get_or_none(StudentStreak.student_id == student_id)
    if row is None:
        return {"current_days": 0, "best_days": 0, "shield_available": True}
    last = row.last_activity_date
    shield_available = row.shield_used_on is None or not _same_iso_week(row.shield_used_on, today)
    # A sequência "conta" se a última atividade foi hoje ou ontem. AUDITORIA P2:
    # se foi ANTEONTEM mas o escudo da semana está disponível, o display também
    # mantém a chama acesa — é exatamente o caso que update_streak preservaria
    # ao estudar hoje; mostrar 0 minaria o propósito psicológico do escudo.
    alive = last in (today, today - datetime.timedelta(days=1))
    if not alive and last == today - datetime.timedelta(days=2) and shield_available:
        alive = True
    return {
        "current_days": row.current_days if alive else 0,
        "best_days": row.best_days or 0,
        "shield_available": shield_available,
    }


def register_daily_activity(student_id, today=None):
    """Gancho único chamado pelos pontos de atividade (answer, progresso, /events,
    tutor-chat): atualiza a sequência e concede o XP 'dia_de_estudo'. Idempotente
    por dia; best-effort. Retorna {streak, xp, achievements}.

    AUDITORIA P2 (perf): a checagem de conquistas (~10 queries) só roda na
    PRIMEIRA atividade do dia (xp > 0) — é o único momento em que a sequência
    muda (e com ela `sequencia_7`); os demais critérios têm checagem própria nos
    seus ganchos (conclusão de módulo, resposta, login retroativo). Sem o gate,
    cada sync de 15s do front pagava a varredura inteira."""
    if not gamification_enabled():
        return {"streak": 0, "xp": 0, "achievements": []}
    today = today or datetime.date.today()
    sid = getattr(student_id, "student_id", student_id)
    try:
        streak = update_streak(sid, today)
    except Exception:
        logger.exception("Falha ao atualizar sequência do aluno %s", sid)
        streak = 0
    xp = award(sid, "dia_de_estudo", today=today)
    achievements = check_achievements(sid, today) if xp > 0 else []
    return {"streak": streak, "xp": xp, "achievements": achievements}


# ---------------------------------------------------------------------------
# Conquistas (catálogo no código)
# ---------------------------------------------------------------------------
def _count_xp_rule(sid, rule):
    return (XpEvents.select().where((XpEvents.student_id == sid) &
                                    (XpEvents.rule == rule)).count())


def _has_mastered_any(sid):
    from edubot.data.models.student_mastery import StudentMastery
    return (StudentMastery.select()
            .where((StudentMastery.student_id == sid) &
                   (StudentMastery.p_mastery >= 0.8)).exists())


def _asked_tutor_count(sid):
    from edubot.data.models.learning_events import LearningEvents
    return (LearningEvents.select()
            .where((LearningEvents.student_id == sid) &
                   (LearningEvents.verb == "asked_tutor")).count())


def _best_streak(sid):
    row = StudentStreak.get_or_none(StudentStreak.student_id == sid)
    return (row.best_days or 0) if row else 0


def _completed_all_course_ovas(sid):
    from edubot.data.models.ovas import OVAs
    from edubot.data.models.offerings import Offerings
    from edubot.data.models.subjects import Subjects
    from edubot.data.models.ova_progress import OVAProgress
    student = Students.get_or_none(Students.student_id == sid)
    if student is None:
        return False
    course_id = student.course_id.course_id if hasattr(student.course_id, "course_id") else student.course_id
    total = (OVAs.select()
             .join(Subjects, on=(OVAs.subject_id == Subjects.subject_id))
             .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
             .where(Offerings.course_id == course_id).count())
    if total == 0:
        return False
    done = (OVAProgress.select()
            .where((OVAProgress.student_id == sid) &
                   (OVAProgress.completed == True)).count())
    return done >= total


def _completed_personalized_ova(sid):
    """Conquista 'no seu formato': respondeu TODAS as questões de alguma OVA de
    reforço personalizada."""
    from edubot.data.models.personalized_ova import PersonalizedOVA, PersonalizedOVAItem
    from edubot.data.models.answers import Answers
    for pova in PersonalizedOVA.select().where(PersonalizedOVA.student_id == sid):
        q_items = [it.question_id for it in PersonalizedOVAItem.select().where(
            (PersonalizedOVAItem.personalized_ova_id == pova) &
            (PersonalizedOVAItem.item_kind == "question")) if it.question_id is not None]
        if not q_items:
            continue
        answered = (Answers.select()
                    .where((Answers.student_id == sid) &
                           (Answers.question_id.in_(q_items))).count())
        if answered >= len(q_items):
            return True
    return False


# id -> (nome_pt, nome_en, critério(sid) -> bool, recompensa opcional)
ACHIEVEMENTS = {
    "primeiro_modulo": ("Primeiro passo", "First step",
                        lambda sid: _count_xp_rule(sid, "modulo_concluido") >= 1),
    "revisor_pontual": ("Revisor pontual", "On-time reviewer",
                        lambda sid: _count_xp_rule(sid, "revisao_em_dia") >= 5),
    "sequencia_7":     ("Semana perfeita", "Perfect week",
                        lambda sid: _best_streak(sid) >= 7),
    "mestre_competencia": ("Mestre de competência", "Competency master",
                           _has_mastered_any),
    "curioso":         ("Curioso", "Curious",
                        lambda sid: _asked_tutor_count(sid) >= 5),
    "trilha_completa": ("Trilha completa", "Full track",
                        _completed_all_course_ovas),
    "no_seu_formato":  ("Do seu jeito", "Your way",
                        _completed_personalized_ova),
    "desafiante":      ("Desafiante", "Challenger",   # dispara na Etapa 9 (R.3)
                        lambda sid: _count_xp_rule(sid, "desafio_tentado") >= 1),
}


def unlocked_ids(sid):
    return {a.achievement_id for a in
            StudentAchievements.select().where(StudentAchievements.student_id == sid)}


def check_achievements(student_id, today=None):
    """Desbloqueia as conquistas cujo critério o aluno já cumpre. Idempotente.
    Retorna a lista de ids recém-desbloqueadas (para o front celebrar)."""
    if not gamification_enabled():
        return []
    sid = getattr(student_id, "student_id", student_id)
    have = unlocked_ids(sid)
    newly = []
    for aid, (_pt, _en, criterion, *_rest) in ACHIEVEMENTS.items():
        if aid in have:
            continue
        try:
            if criterion(sid):
                StudentAchievements.create(student_id=sid, achievement_id=aid,
                                           unlocked_at=datetime.datetime.now())
                newly.append(aid)
        except Exception:
            logger.exception("Falha ao checar conquista %s do aluno %s", aid, sid)
    return newly


def achievements_state(student_id, lang="pt"):
    """Vitrine: todas as conquistas com estado (unlocked) + rótulo. Mostra o
    caminho (locked com nome) é o que engaja."""
    sid = getattr(student_id, "student_id", student_id)
    have = unlocked_ids(sid)
    out = []
    for aid, (pt, en, *_rest) in ACHIEVEMENTS.items():
        out.append({"id": aid, "nome": en if lang == "en" else pt,
                    "unlocked": aid in have})
    return out


# ---------------------------------------------------------------------------
# Ranking semanal opt-in (G.4)
# ---------------------------------------------------------------------------
def _course_active_weekly_xp(course_id, week_start):
    """{student_id: xp_semana} dos alunos do curso com XP na semana. 1 query."""
    week_end = week_start + datetime.timedelta(days=6)
    rows = (XpEvents
            .select(XpEvents.student_id, fn.SUM(XpEvents.points).alias("xp"))
            .join(Students, on=(XpEvents.student_id == Students.student_id))
            .where((Students.course_id == course_id) & (Students.role == "aluno") &
                   (XpEvents.awarded_on >= week_start) & (XpEvents.awarded_on <= week_end))
            .group_by(XpEvents.student_id)
            .dicts())
    # int(): normaliza o Decimal do SUM (MySQL) — evita XP como string no JSON
    # e Decimal na aritmética do nível.
    return {r["student_id"]: int(r["xp"] or 0) for r in rows}


def _ranking_participants(course_id):
    """ids dos alunos do curso que consentiram o ranking (opt-in) E têm apelido."""
    from edubot.data.models.consents import Consents
    rows = (Consents
            .select(Consents.student_id)
            .join(Students, on=(Consents.student_id == Students.student_id))
            .where((Students.course_id == course_id) &
                   (Consents.purpose == "ranking_turma") & (Consents.granted == True)))
    return {c.student_id.student_id if hasattr(c.student_id, "student_id") else c.student_id
            for c in rows}


def leaderboard(student, week_start=None, size=None):
    """Ranking semanal da turma. Público = só quem fez opt-in (apelido). `me`
    sempre vê a própria posição/percentil no cohort do curso (mesmo sem opt-in)."""
    size = size or int(os.getenv("EDUBOT_LEADERBOARD_SIZE", "10"))
    week_start = week_start or _week_start()
    sid = student.student_id
    course_id = student.course_id.course_id if hasattr(student.course_id, "course_id") else student.course_id

    xp_map = _course_active_weekly_xp(course_id, week_start)
    me_xp = xp_map.get(sid, 0)

    # posição do aluno no cohort do curso (todos os ativos), para motivar o opt-in.
    # top_percent = "top X%" (menor é melhor): #1 de 10 -> 10%.
    total = len(xp_map) or 1
    better = sum(1 for v in xp_map.values() if v > me_xp)
    me_rank = better + 1 if me_xp > 0 else None
    top_percent = round(100 * me_rank / total) if me_rank else None

    participants = _ranking_participants(course_id)
    nick_by_id = {}
    if participants:
        nick_by_id = {s.student_id: s.nickname for s in
                      Students.select(Students.student_id, Students.nickname)
                      .where(Students.student_id.in_(list(participants)))}

    board = sorted(((pid, xp_map.get(pid, 0)) for pid in participants),
                   key=lambda kv: -kv[1])[:size]
    top = [{
        "apelido": nick_by_id.get(pid) or "—",
        "xp_semana": xp,
        "nivel": level_from_xp(xp_total(pid)),
        "eu": pid == sid,
    } for pid, xp in board if xp > 0]

    return {
        "week_start": str(week_start),
        "participando": sid in participants,
        "top": top,
        "me": {"rank": me_rank, "top_percent": top_percent, "xp_semana": me_xp,
               "nivel": level_from_xp(xp_total(sid))},
    }


def available_titles(student_id, lang="pt"):
    """Títulos que o aluno GANHOU (das conquistas desbloqueadas) — o que ele pode
    escolher como título ativo (R.2)."""
    have = unlocked_ids(student_id)
    out = []
    for aid, (pt, en) in TITLE_BY_ACHIEVEMENT.items():
        if aid in have:
            out.append({"id": aid, "titulo": en if lang == "en" else pt})
    return out


def set_title(student, title_id):
    """Define o título ativo do aluno, se ele o ganhou. Retorna o título ou None.
    title_id vazio/None limpa o título. Grava o rótulo PT (legível no banco); a
    exibição é traduzida em me_state via _title_id_from_label."""
    if not title_id:
        student.title = None
        student.save()
        return None
    earned = {t["id"] for t in available_titles(student.student_id)}
    if title_id not in earned:
        return None
    label = TITLE_BY_ACHIEVEMENT[title_id][0]
    student.title = label
    student.save()
    return label


def _title_id_from_label(label):
    """Reverse lookup do rótulo gravado (PT ou EN) -> id do título. AUDITORIA P2:
    sem isto, a UI em inglês não conseguia casar o título ativo com as opções
    (gravamos o rótulo PT) e exibia o rótulo sem tradução."""
    if not label:
        return None
    for aid, (pt, en) in TITLE_BY_ACHIEVEMENT.items():
        if label in (pt, en):
            return aid
    return None


def personas_state(level=None):
    """Estado das personas de avatar — AV.1 (Plano 3): LIVRES para todos. `level`
    é ignorado (mantido na assinatura por compat); `unlock_level`/`unlocked` seguem
    no shape por 1 release para não quebrar front em cache."""
    return [{"id": pid, "unlock_level": 0, "unlocked": True} for pid in PERSONA_IDS]


def me_state(student, lang="pt"):
    """Payload do cabeçalho de jornada (GET /gamification/me)."""
    sid = student.student_id
    total = xp_total(sid)
    prog = level_progress(total)
    # título: id resolvido do rótulo gravado + rótulo TRADUZIDO para a UI
    title_id = _title_id_from_label(student.title)
    if title_id:
        pt, en = TITLE_BY_ACHIEVEMENT[title_id]
        title_label = en if lang == "en" else pt
    else:
        title_label = student.title
    return {
        "enabled": gamification_enabled(),
        **prog,
        "xp_week": xp_week(sid),
        "streak": streak_state(sid),
        "achievements": achievements_state(sid, lang),
        "personas": personas_state(prog["level"]),
        "available_titles": available_titles(sid, lang),
        "title": title_label,
        "title_id": title_id,
        "nickname": student.nickname,
    }
