"""Plano de Rastreabilidade — Fase 4: o ciclo do reforço fecha sozinho.

Antes, a OVA de reforço só nascia se o aluno fosse por conta própria à aba
"Reforço" — justamente o que o aluno em dificuldade não faz. E o alvo era
sempre a competência mais fraca GLOBAL, então terminar mal o OVA de Cálculo
podia gerar reforço de Nuvem.
"""
import datetime
import json

from edubot.data.models.competencies import Competencies
from edubot.data.models.interventions import Interventions
from edubot.data.models.questions import Questions
from edubot.data.models.resources import Resources
from edubot.data.models.student_mastery import StudentMastery
from edubot.services.coverage import competency_coverage, coverage_gaps
from edubot.services.reinforcement import (INTERVENTION_TYPE,
                                           REINFORCEMENT_MASTERY_THRESHOLD,
                                           suggest_for_ova, suggest_reinforcement)


def _interventions_de_reforco(student_id=1):
    return list(Interventions
                .select()
                .where((Interventions.student_id == student_id) &
                       (Interventions.type == INTERVENTION_TYPE)))


def test_dominio_baixo_cria_convite_de_reforco(seeded_db):
    criada = suggest_reinforcement(1, 1, "Comp A", 0.1)
    assert criada is not None
    # A competência alvo viaja na descrição: é o que o CTA usa para abrir a
    # trilha já apontada para o assunto certo.
    assert "[comp:1]" in criada.description
    assert len(_interventions_de_reforco()) == 1


def test_dominio_suficiente_nao_incomoda_o_aluno(seeded_db):
    assert suggest_reinforcement(1, 1, "Comp A", REINFORCEMENT_MASTERY_THRESHOLD) is None
    assert suggest_reinforcement(1, 1, "Comp A", 0.95) is None
    assert _interventions_de_reforco() == []


def test_nao_repete_a_cobranca_dentro_do_cooldown(seeded_db):
    suggest_reinforcement(1, 1, "Comp A", 0.1)
    suggest_reinforcement(1, 1, "Comp A", 0.1)
    assert len(_interventions_de_reforco()) == 1


def test_cobra_de_novo_depois_do_cooldown(seeded_db):
    hoje = datetime.date.today()
    suggest_reinforcement(1, 1, "Comp A", 0.1, today=hoje - datetime.timedelta(days=30))
    suggest_reinforcement(1, 1, "Comp A", 0.1, today=hoje)
    assert len(_interventions_de_reforco()) == 2


def test_reforco_do_ova_olha_as_competencias_daquele_ova(seeded_db):
    """O ponto da Fase 4: o reforço é sobre o que o aluno ACABOU de estudar."""
    # Competência 2 é fraca, mas NÃO pertence ao OVA 1.
    Competencies.create(competency_id=2, competency_description="Comp B", subject_id=1)
    StudentMastery.create(student_id=1, competency_id=1, p_mastery=0.1,
                          attempts_seen=3, updated_at=datetime.datetime.now())
    StudentMastery.create(student_id=1, competency_id=2, p_mastery=0.05,
                          attempts_seen=3, updated_at=datetime.datetime.now())

    assert suggest_for_ova(1, 1) == 1
    criadas = _interventions_de_reforco()
    assert len(criadas) == 1
    assert "[comp:1]" in criadas[0].description  # a do OVA, não a pior global


def test_ova_com_dominio_ok_nao_gera_reforco(seeded_db):
    StudentMastery.create(student_id=1, competency_id=1, p_mastery=0.9,
                          attempts_seen=5, updated_at=datetime.datetime.now())
    assert suggest_for_ova(1, 1) == 0


# --- alvo explícito na geração da trilha ------------------------------------

def test_gerar_reforco_aceita_competencia_alvo(client, auth):
    resp = client.post("/edubot/personalized-ova", headers=auth(1),
                       data=json.dumps({"competency_id": 1}))
    assert resp.status_code == 201
    assert json.loads(resp.data)["target_competency_id"] == 1


def test_gerar_reforco_sem_corpo_continua_funcionando(client, auth):
    """Degradação segura: a chamada histórica (sem corpo) não pode quebrar."""
    assert client.post("/edubot/personalized-ova", headers=auth(1)).status_code == 201


def test_competencia_de_outro_curso_e_rejeitada(client, auth):
    resp = client.post("/edubot/personalized-ova", headers=auth(1),
                       data=json.dumps({"competency_id": 9999}))
    assert resp.status_code == 400


# --- cobertura de conteúdo (§6.2) -------------------------------------------

def test_cobertura_acusa_competencia_sem_material(seeded_db):
    """A competência do seed tem 2 questões e nenhum recurso classificado —
    exatamente o tipo de lacuna que impede o reforço de funcionar."""
    lacunas = coverage_gaps()
    assert any(item["competency_id"] == 1 for item in lacunas)
    item = next(i for i in lacunas if i["competency_id"] == 1)
    assert item["questoes"] == 2      # < MIN_QUESTIONS
    assert item["formatos"] == []     # nenhum formato de remediação


def test_cobertura_ok_quando_o_invariante_e_atendido(seeded_db):
    Questions.create(question_id=3, statement="4+4?",
                     alternatives={"alternatives": ["8", "9"]}, answer="a",
                     ova_id=1, competency_id=1)
    Resources.create(resource_id=10, ova_id=1, resource_type="video",
                     resource_title="V", resource_url="u", competency_id=1)
    Resources.create(resource_id=11, ova_id=1, resource_type="texto",
                     resource_title="T", resource_url="u", competency_id=1)

    item = next(i for i in competency_coverage() if i["competency_id"] == 1)
    assert item["questoes"] == 3
    assert set(item["formatos"]) == {"video", "texto"}
    assert item["ok"] is True
