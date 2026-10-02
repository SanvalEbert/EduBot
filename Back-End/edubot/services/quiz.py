"""Serviço de quiz — lógica compartilhada de questões (A.6 / U.1).

Reúne `alternatives_list` (era duplicada em questionRoute e personalizedOvaRoute —
mesmo padrão do A15) e a regra de liberação do quiz por consumo (U.1).
"""
import json

from edubot.data.models.ova_progress import OVAProgress


def alternatives_list(question, lang="pt"):
    """Alternativas da questão como lista de strings, no idioma pedido.

    Aceita o JSONField tanto como dict (MySQL) quanto como string (fallback
    SQLite dev). Com lang="en" e tradução disponível, serve alternatives_en na
    MESMA ordem do PT — o gabarito por letra continua válido. NUNCA expõe o
    gabarito ao cliente.
    """
    alternatives = question.alternatives
    if lang == "en" and question.alternatives_en:
        alternatives = question.alternatives_en
    if isinstance(alternatives, str):
        alternatives = json.loads(alternatives)
    return alternatives["alternatives"]


# --- D.4: pool adaptativo por dificuldade × domínio (mastery) --------------
# Teto de dificuldade liberado por faixa de domínio (zona proximal): o difícil
# (3) só entra quando o aluno já domina a competência; senão fica em fácil+média.
DEVELOPING_MASTERY = 0.4
DEVELOPED_MASTERY = 0.8


def difficulty_ceiling(mastery):
    """Dificuldade máxima liberada dado o domínio estimado (D.2) da competência.

    `mastery` None (sem sinal ainda) trata como baixo → teto média (2)."""
    if mastery is not None and mastery >= DEVELOPED_MASTERY:
        return 3           # domina → inclui difíceis
    return 2               # iniciante/intermediário → fácil + média


def adaptive_pool(questions, mastery_by_competency, difficulty_overrides=None):
    """Filtra e ORDENA as questões do OVA para a zona proximal do aluno (D.4/B.5).

    - teto por competência: se há OVERRIDE de dificuldade (B.5 —
      `student_difficulty`), o teto é `min(3, level+1)`; senão, deriva do domínio
      (D.4: domina ≥0.8 → inclui difícil);
    - mantém questões com `difficulty <= teto`;
    - ordena por dificuldade ascendente (fáceis primeiro), estável por question_id;
    - degradação segura: se TODAS forem filtradas, devolve o pool original
      ordenado — nunca um quiz vazio.

    `questions`: iterável de Questions. `mastery_by_competency`: {competency_id:
    p_mastery}. `difficulty_overrides`: {competency_id: level} (opcional)."""
    qs = list(questions)
    overrides = difficulty_overrides or {}

    def _cid(q):
        c = q.competency_id
        return c.competency_id if hasattr(c, "competency_id") else c

    def _diff(q):
        return getattr(q, "difficulty", 2) or 2

    def _ceiling(cid):
        if cid in overrides:
            return max(1, min(3, overrides[cid] + 1))   # B.5: override do tutor/agente
        return difficulty_ceiling(mastery_by_competency.get(cid))

    filtered = [q for q in qs if _diff(q) <= _ceiling(_cid(q))]
    pool = filtered or qs   # nunca devolve quiz vazio
    return sorted(pool, key=lambda q: (_diff(q), q.question_id))


def difficulty_overrides_for(student_id):
    """{competency_id: level} dos overrides de dificuldade do aluno (B.5)."""
    from edubot.data.models.student_difficulty import StudentDifficulty
    return {d.competency_id.competency_id if hasattr(d.competency_id, "competency_id")
            else d.competency_id: d.level
            for d in StudentDifficulty.select().where(StudentDifficulty.student_id == student_id)}


CHALLENGE_DIFFICULTY = 3
MASTERED_THRESHOLD = 0.8


def challenge_pool(questions, mastery_by_competency):
    """R.3 (Plano 2) — modo desafio: só as questões DIFÍCEIS (difficulty=3) de
    competências que o aluno DOMINA (BKT >= 0.8). Retorna [] quando não há —
    a rota traduz isso em 403 (challenge_locked), como o gate U.1."""
    def _cid(q):
        c = q.competency_id
        return c.competency_id if hasattr(c, "competency_id") else c

    def _diff(q):
        return getattr(q, "difficulty", 2) or 2

    pool = [q for q in questions
            if _diff(q) == CHALLENGE_DIFFICULTY
            and (mastery_by_competency.get(_cid(q)) or 0) >= MASTERED_THRESHOLD]
    return sorted(pool, key=lambda q: q.question_id)


def quiz_unlocked(student, ova):
    """U.1 — o quiz do módulo só libera após consumir o conteúdo.

    Regra: o aluno precisa ter lido >= `ova.quiz_gate_perc`% do OVA
    (perc_scrolled). `quiz_gate_perc == 0` desliga o gate (conteúdo curto/
    introdutório). Validado NO BACKEND — não é só esconder o botão no front.

    Retorna (unlocked: bool, info: dict|None). `info` traz {gate, perc} para o
    front explicar o motivo do bloqueio ("leia 70% — você está em 35%")."""
    gate = getattr(ova, "quiz_gate_perc", 0) or 0
    if gate <= 0:
        return True, None
    progress = OVAProgress.get_or_none(
        (OVAProgress.student_id == student) & (OVAProgress.ova_id == ova))
    perc = (progress.perc_scrolled or 0) if progress else 0
    return perc >= gate, {"gate": gate, "perc": perc}
