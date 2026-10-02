"""Plano de Rastreabilidade — Fase 3: risco composto (auditoria P9).

A regra anterior era `taxa_erro > 0.5`. Ela enxerga só uma forma de dificuldade
e ignora quem sumiu — quem não tenta não erra, então some do radar exatamente
quem mais precisa de atenção.

Os testes abaixo fixam as duas metades do contrato:
  1. o que a regra antiga via, o score novo continua vendo (sem regressão);
  2. o que a regra antiga NÃO via, o score novo passa a ver.
"""
from edubot.services.risk import (RISK_THRESHOLD, WEIGHT_DUE_REVIEWS,
                                  WEIGHT_ERROR_RATE, WEIGHT_INACTIVITY,
                                  WEIGHT_LOW_CONSUMPTION, WEIGHT_MASTERY_DROP,
                                  compute_risk)

MAX_SCORE = (WEIGHT_ERROR_RATE + WEIGHT_INACTIVITY + WEIGHT_MASTERY_DROP
             + WEIGHT_DUE_REVIEWS + WEIGHT_LOW_CONSUMPTION)


def test_aluno_saudavel_nao_pontua():
    risco = compute_risk(taxa_erro=0.1, dias_sem_acesso=0, revisoes_vencidas=0,
                         consumo_perc=90, tendencia_queda=0)
    assert risco["score"] == 0
    assert risco["em_risco"] is False
    assert risco["principal"] is None


def test_sem_dados_nao_e_risco():
    """Ausência de informação não é sinal de risco (aluno recém-matriculado)."""
    assert compute_risk()["em_risco"] is False


def test_erro_alto_com_consumo_baixo_continua_sendo_risco():
    """Sem regressão: o caso que a regra antiga (taxa_erro > 0.5) já pegava."""
    risco = compute_risk(taxa_erro=1.0, dias_sem_acesso=0, consumo_perc=0)
    assert risco["em_risco"] is True
    assert risco["principal"] == "erro_quiz"


def test_aluno_que_sumiu_entra_no_radar():
    """O ganho da Fase 3: taxa_erro é None (não tentou nada), mas ele sumiu.

    Pela regra antiga este aluno era invisível."""
    risco = compute_risk(taxa_erro=None, dias_sem_acesso=20, consumo_perc=10,
                         revisoes_vencidas=3)
    assert risco["em_risco"] is True
    assert risco["principal"] == "inatividade"
    assert "erro_quiz" not in risco["componentes"]


def test_esquecimento_conta_como_risco():
    """Domínio caindo em várias competências + revisões acumuladas.

    Outro caso invisível para a regra antiga: o aluno até acerta o que tenta,
    mas está DESAPRENDENDO o que já sabia."""
    risco = compute_risk(tendencia_queda=3, revisoes_vencidas=5, consumo_perc=35)
    assert risco["componentes"]["dominio_caindo"] == WEIGHT_MASTERY_DROP
    assert risco["componentes"]["revisoes_vencidas"] == WEIGHT_DUE_REVIEWS
    assert risco["em_risco"] is True


def test_errar_um_pouco_nao_penaliza():
    """Abaixo do piso, errar faz parte de aprender."""
    assert "erro_quiz" not in compute_risk(taxa_erro=0.25)["componentes"]


def test_sinais_saturam_no_teto():
    """Um sinal extremo não pode estourar o peso e dominar o score."""
    risco = compute_risk(dias_sem_acesso=999, revisoes_vencidas=999,
                         tendencia_queda=999, taxa_erro=1.0, consumo_perc=0)
    assert risco["score"] == MAX_SCORE
    assert risco["componentes"]["inatividade"] == WEIGHT_INACTIVITY


def test_componentes_explicam_o_score():
    """O professor precisa saber POR QUE, não só QUANTO."""
    risco = compute_risk(taxa_erro=0.9, dias_sem_acesso=12)
    assert risco["score"] == sum(risco["componentes"].values())
    assert risco["score"] >= RISK_THRESHOLD
    assert set(risco["componentes"]) == {"erro_quiz", "inatividade"}
