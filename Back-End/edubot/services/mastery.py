"""Modelo do aluno por competência (D.2) — Bayesian Knowledge Tracing + decaimento.

BKT clássico de 4 parâmetros (init/learn/slip/guess). A cada tentativa:
  1. aplica decaimento ao p_mastery pelo tempo sem prática (esquecimento);
  2. corrige a estimativa pela evidência (acertou/errou), via Bayes;
  3. aplica a transição de aprendizado (P_LEARN).

Substitui o limiar binário acertos/total do student_context: p_mastery é um
sinal contínuo e estável (considera nº de tentativas, ordem e tempo). Os
parâmetros ficam em constantes ajustáveis pela equipe pedagógica — mesmo espírito
dos thresholds do student_context.
"""
import datetime

from edubot.data.models.student_mastery import StudentMastery

# Parâmetros do BKT (ajustáveis). Valores conservadores e clássicos:
P_INIT = 0.20    # domínio a priori (aluno "novo" na competência)
P_LEARN = 0.15   # chance de aprender de uma tentativa para a próxima
P_SLIP = 0.10    # chance de errar sabendo (deslize)
P_GUESS = 0.25   # chance de acertar sem saber (chute em múltipla escolha)
DECAY_PER_WEEK = 0.02  # esquecimento: p_mastery decai por semana sem prática

# Limiares dos 3 rótulos da UI (mantidos), agora derivados de p_mastery.
DEVELOPING_THRESHOLD = 0.40
DEVELOPED_THRESHOLD = 0.80


def _get_or_init(student_id, competency_id):
    """Retorna (row, is_new). `is_new` decide INSERT vs UPDATE no save — com chave
    composta o Peewee não infere isso sozinho."""
    row = StudentMastery.get_or_none((StudentMastery.student_id == student_id) &
                                     (StudentMastery.competency_id == competency_id))
    if row is None:
        row = StudentMastery(student_id=student_id, competency_id=competency_id,
                             p_mastery=P_INIT, attempts_seen=0,
                             updated_at=datetime.datetime.now())
        return row, True
    return row, False


def _apply_decay(p_mastery, updated_at, now=None):
    """Decai o p_mastery em direção ao P_INIT pelo tempo sem prática. Um aluno que
    dominava e sumiu por semanas volta com estimativa menor (esquecimento)."""
    if not updated_at:
        return p_mastery
    now = now or datetime.datetime.now()
    if isinstance(updated_at, str):
        try:
            updated_at = datetime.datetime.fromisoformat(updated_at)
        except ValueError:
            return p_mastery
    weeks = max(0.0, (now - updated_at).total_seconds() / (7 * 24 * 3600))
    decay = min(1.0, weeks * DECAY_PER_WEEK)
    # decai proporcionalmente ao excedente sobre P_INIT (não decai abaixo do a priori)
    return p_mastery - (p_mastery - P_INIT) * decay


def update_on_attempt(student_id, competency_id, is_correct, now=None):
    """Atualiza p_mastery após uma tentativa (1 upsert). Retorna o novo p_mastery.

    Chamado sincronamente por /question/answer e pelo backfill do histórico."""
    now = now or datetime.datetime.now()
    row, is_new = _get_or_init(student_id, competency_id)
    p = _apply_decay(row.p_mastery, row.updated_at, now)

    # Passo de correção (Bayes): P(domina | evidência)
    if is_correct:
        num = p * (1 - P_SLIP)
        den = num + (1 - p) * P_GUESS
    else:
        num = p * P_SLIP
        den = num + (1 - p) * (1 - P_GUESS)
    p_given = num / den if den else p

    # Passo de aprendizado (transição)
    row.p_mastery = p_given + (1 - p_given) * P_LEARN
    row.attempts_seen += 1
    row.updated_at = now
    row.save(force_insert=is_new)
    return row.p_mastery


def status_from_mastery(p_mastery):
    """Mapeia p_mastery -> os 3 rótulos da UI (mantém o contrato do front)."""
    if p_mastery is None:
        return None
    if p_mastery >= DEVELOPED_THRESHOLD:
        return "desenvolvida"
    if p_mastery >= DEVELOPING_THRESHOLD:
        return "em desenvolvimento"
    return "não iniciada"


def mastery_map(student_id):
    """{competency_id: p_mastery} do aluno — para o perfil e as tools do agente."""
    return {m.competency_id.competency_id if hasattr(m.competency_id, "competency_id")
            else m.competency_id: m.p_mastery
            for m in StudentMastery.select().where(StudentMastery.student_id == student_id)}


# --- H.1 (Plano 2): histórico diário de domínio + tendência -----------------
def snapshot_today(today=None):
    """Grava o snapshot diário do domínio de cada (aluno, competência) que tem
    linha em student_mastery. Idempotente (PK composto por dia): rodar 2× no
    mesmo dia atualiza o valor, não duplica. Retorna quantas linhas gravou.
    Chamado pelo sweep diário."""
    from edubot.data.models.student_mastery_history import StudentMasteryHistory
    today = today or datetime.date.today()
    n = 0
    for m in StudentMastery.select():
        sid = m.student_id.student_id if hasattr(m.student_id, "student_id") else m.student_id
        cid = m.competency_id.competency_id if hasattr(m.competency_id, "competency_id") else m.competency_id
        row = StudentMasteryHistory.get_or_none(
            (StudentMasteryHistory.student_id == sid) &
            (StudentMasteryHistory.competency_id == cid) &
            (StudentMasteryHistory.snapshot_date == today))
        if row is None:
            StudentMasteryHistory(student_id=sid, competency_id=cid,
                                  snapshot_date=today, p_mastery=m.p_mastery).save(force_insert=True)
            n += 1
        else:
            row.p_mastery = m.p_mastery
            row.save()
    return n


def mastery_trend(student_id, days=7, today=None):
    """{competency_id: {atual, anterior, delta, direcao}} — variação do domínio
    na janela. `anterior` = snapshot MAIS ANTIGO dentro dos últimos `days` dias;
    `atual` = domínio corrente (student_mastery). Só competências com baseline no
    período (senão não há o que comparar)."""
    from edubot.data.models.student_mastery_history import StudentMasteryHistory
    today = today or datetime.date.today()
    floor = today - datetime.timedelta(days=days)

    baseline = {}
    for h in (StudentMasteryHistory
              .select()
              .where((StudentMasteryHistory.student_id == student_id) &
                     (StudentMasteryHistory.snapshot_date >= floor))
              .order_by(StudentMasteryHistory.snapshot_date)):
        cid = h.competency_id.competency_id if hasattr(h.competency_id, "competency_id") else h.competency_id
        baseline.setdefault(cid, h.p_mastery)   # 1ª (mais antiga) por competência

    trend = {}
    for cid, atual in mastery_map(student_id).items():
        base = baseline.get(cid)
        if base is None:
            continue
        delta = round(atual - base, 2)
        trend[cid] = {
            "atual": round(atual, 2),
            "anterior": round(base, 2),
            "delta": delta,
            "direcao": "up" if delta > 0.02 else "down" if delta < -0.02 else "flat",
        }
    return trend
