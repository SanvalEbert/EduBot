"""Gatilhos do reforço (Plano de Rastreabilidade — Fase 4).

Diagnóstico da auditoria (§6.1): a OVA de reforço existia e funcionava, mas só
nascia de um CLIQUE do aluno na aba "Reforço". O requisito pedagógico — "reforço
disparado quando o desempenho na competência for insuficiente" — nunca fechava:
o aluno que mais precisa é justamente o que não vai atrás.

Aqui mora a regra que fecha o ciclo. Quando o domínio de uma competência cai
abaixo do limiar, criamos uma INTERVENÇÃO com a competência alvo. O aluno vê o
convite no dashboard e um clique gera a trilha já apontada para o assunto certo.

Por que não gerar a OVA automaticamente: montar a trilha roda o agente
(tool-use). No mock isso é grátis, mas com LLM real seria custo por gatilho, sem
garantia de que o aluno vá usar. A geração continua no clique — o que a Fase 4
muda é o aluno passar a ser CHAMADO, com o alvo certo já decidido.
"""
import datetime
import logging

from edubot.data.models.interventions import Interventions
from edubot.services.events import emit

logger = logging.getLogger("edubot.reinforcement")

# Abaixo deste domínio (BKT) a competência é considerada insuficiente. Alinhado
# ao DEVELOPING_THRESHOLD do mastery.py — abaixo disso a UI já rotula a
# competência como "não iniciada"/frágil.
REINFORCEMENT_MASTERY_THRESHOLD = 0.4

# Uma cobrança por competência a cada 7 dias: o aluno precisa de tempo para
# fazer o reforço antes de ser chamado de novo (e o professor não quer o painel
# cheio da mesma intervenção).
REINFORCEMENT_COOLDOWN_DAYS = 7

INTERVENTION_TYPE = "reforco_sugerido"


def _recent_intervention_exists(student_id, competency_id, today):
    """Já cobramos esta competência dentro do cooldown?"""
    floor = today - datetime.timedelta(days=REINFORCEMENT_COOLDOWN_DAYS)
    for row in (Interventions
                .select()
                .where((Interventions.student_id == student_id) &
                       (Interventions.type == INTERVENTION_TYPE) &
                       (Interventions.date >= floor))):
        if f"[comp:{competency_id}]" in (row.description or ""):
            return True
    return False


def suggest_reinforcement(student_id, competency_id, competency_name, p_mastery,
                          today=None):
    """Cria a intervenção de reforço se o domínio estiver insuficiente.

    Retorna a linha criada, ou None quando não havia o que fazer (domínio ok ou
    já cobrado recentemente). Best-effort: nunca levanta para o chamador, que
    está no caminho de escrita do quiz/progresso."""
    try:
        if p_mastery is None or p_mastery >= REINFORCEMENT_MASTERY_THRESHOLD:
            return None
        today = today or datetime.date.today()
        if _recent_intervention_exists(student_id, competency_id, today):
            return None

        nome = competency_name or "esta competência"
        # A marca [comp:N] é o que permite o CTA do front abrir a trilha já
        # apontada para a competência certa (e a dedup achar a cobrança anterior).
        descricao = (f"Percebi dificuldade em \"{nome}\". Preparei um reforço "
                     f"focado nesse assunto — quer praticar agora? [comp:{competency_id}]")
        created = Interventions.create(
            student_id=student_id, date=today, type=INTERVENTION_TYPE,
            description=descricao, result="pendente")
        emit(student_id, "received_intervention", "intervention",
             created.intervention_id, tipo=INTERVENTION_TYPE,
             competency_id=competency_id, trigger="mastery_drop")
        return created
    except Exception:
        logger.exception("Falha ao sugerir reforço (aluno=%s comp=%s)",
                         student_id, competency_id)
        return None


def suggest_for_ova(student_id, ova_id, today=None):
    """Gatilho 2: ao CONCLUIR um OVA, avalia só as competências DAQUELE OVA.

    É o que evita o desalinhamento que a auditoria apontou: terminar o OVA de
    Cálculo com dificuldade gerava reforço de Nuvem (a competência mais fraca
    global). Aqui o reforço é sobre o que o aluno acabou de estudar.

    Retorna quantas intervenções criou. Best-effort."""
    from edubot.data.models.competencies import Competencies
    from edubot.data.models.questions import Questions
    from edubot.services.mastery import mastery_map

    try:
        competencias = {
            row.competency_id.competency_id: row.competency_id.competency_description
            for row in (Questions
                        .select(Questions.competency_id)
                        .join(Competencies,
                              on=(Questions.competency_id == Competencies.competency_id))
                        .where(Questions.ova_id == ova_id)
                        .distinct())
        }
        if not competencias:
            return 0
        dominios = mastery_map(student_id)
        criadas = 0
        for competency_id, nome in competencias.items():
            if suggest_reinforcement(student_id, competency_id, nome,
                                     dominios.get(competency_id), today=today):
                criadas += 1
        return criadas
    except Exception:
        logger.exception("Falha ao sugerir reforço do OVA %s (aluno=%s)",
                         ova_id, student_id)
        return 0
