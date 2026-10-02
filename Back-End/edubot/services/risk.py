"""Risco do aluno (Plano de Rastreabilidade — Fase 3, corrige a auditoria P9).

O painel classificava "em risco" só por `taxa_erro > 0.5`. Isso deixa passar o
aluno que sumiu (não erra porque não tenta), o que vem esquecendo o que sabia e o
que acumula revisões vencidas — e ainda trata como igual quem errou muito num
único quiz difícil.

O score combina os cinco sinais que a plataforma já mede, cada um contribuindo no
máximo com o seu peso. Duas decisões importantes:

  - os PESOS são constantes nomeadas: a calibração é pedagógica, não técnica, e a
    equipe precisa conseguir ajustá-los sem ler o algoritmo;
  - o retorno traz os COMPONENTES, não só o total. Um número sozinho não ajuda o
    professor a agir — ele precisa saber se o aluno está em risco por ausência ou
    por dificuldade, porque a intervenção é diferente em cada caso.
"""

# Contribuição MÁXIMA de cada sinal (não é uma partição de 100: são tetos
# independentes). Calibração pedagógica — ajuste aqui, não no algoritmo.
#
# REGRA DE CALIBRAÇÃO: o score novo não pode DEIXAR DE VER quem a regra antiga
# (taxa_erro > 0.5) já via. Um aluno errando quase tudo e sem consumir material
# tem de cruzar o limiar sozinho; os demais sinais existem para ACRESCENTAR
# detecção (o aluno que sumiu, o que está esquecendo), nunca para subtrair.
WEIGHT_ERROR_RATE = 30      # erra muito no quiz
WEIGHT_INACTIVITY = 30      # sumiu
# Domínio caindo é o sinal MAIS DIRETO de perda de aprendizado (o aluno está
# desaprendendo, não apenas errando), por isso pesa mais que revisão/consumo.
WEIGHT_MASTERY_DROP = 25    # está esquecendo (tendência de domínio em queda)
WEIGHT_DUE_REVIEWS = 15     # acumula revisões vencidas
WEIGHT_LOW_CONSUMPTION = 15 # não consome o material

# A partir daqui o aluno aparece como "em risco" no painel.
RISK_THRESHOLD = 40

# Saturações: a partir destes valores o sinal já contribui com o peso inteiro.
INACTIVITY_DAYS_MAX = 10    # 10 dias sem acesso = ausência que exige ação
DUE_REVIEWS_MAX = 5         # 5 revisões vencidas = descontrole
LOW_CONSUMPTION_PERC = 40   # abaixo disso o consumo é considerado insuficiente
ERROR_RATE_FLOOR = 0.3      # errar um pouco é aprender; abaixo disso não pesa
ERROR_RATE_CEILING = 0.6    # daqui para cima o erro já é o teto do sinal


def _scaled(value, maximum, weight):
    """Converte um sinal 0..maximum em 0..weight, saturando no topo."""
    if not value or maximum <= 0:
        return 0.0
    return min(1.0, value / maximum) * weight


def compute_risk(*, taxa_erro=None, dias_sem_acesso=None, revisoes_vencidas=0,
                 consumo_perc=None, tendencia_queda=0):
    """Score de risco 0..100 + a contribuição de cada sinal.

    Todos os parâmetros são opcionais: um aluno sem histórico simplesmente não
    pontua naquele componente (ausência de dado não é sinal de risco).

    `tendencia_queda` é a quantidade de competências cuja tendência de domínio
    está caindo (vem de mastery.mastery_trend)."""
    componentes = {}

    # Erro no quiz: só conta acima de um piso — errar um pouco é aprender.
    if taxa_erro is not None and taxa_erro > ERROR_RATE_FLOOR:
        faixa = ERROR_RATE_CEILING - ERROR_RATE_FLOOR
        excedente = (taxa_erro - ERROR_RATE_FLOOR) / faixa
        componentes["erro_quiz"] = round(min(1.0, excedente) * WEIGHT_ERROR_RATE, 1)

    if dias_sem_acesso:
        componentes["inatividade"] = round(
            _scaled(dias_sem_acesso, INACTIVITY_DAYS_MAX, WEIGHT_INACTIVITY), 1)

    if tendencia_queda:
        # 3+ competências caindo já caracteriza esquecimento generalizado.
        componentes["dominio_caindo"] = round(
            _scaled(tendencia_queda, 3, WEIGHT_MASTERY_DROP), 1)

    if revisoes_vencidas:
        componentes["revisoes_vencidas"] = round(
            _scaled(revisoes_vencidas, DUE_REVIEWS_MAX, WEIGHT_DUE_REVIEWS), 1)

    if consumo_perc is not None and consumo_perc < LOW_CONSUMPTION_PERC:
        falta = (LOW_CONSUMPTION_PERC - consumo_perc) / LOW_CONSUMPTION_PERC
        componentes["consumo_baixo"] = round(falta * WEIGHT_LOW_CONSUMPTION, 1)

    score = round(sum(componentes.values()))
    return {
        "score": score,
        "em_risco": score >= RISK_THRESHOLD,
        "componentes": componentes,
        # O sinal que mais pesa é o que o professor deve atacar primeiro.
        "principal": max(componentes, key=componentes.get) if componentes else None,
    }
