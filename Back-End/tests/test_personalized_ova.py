"""A.7 — OVA personalizada: criação pelo agente (mock), validação server-side de
IDs escolhidos pelo modelo e isolamento por dono."""
import json

import pytest

from edubot.agent.tools import criar_ova_personalizada, listar_recursos_remediacao
from edubot.data.models.competencies import Competencies
from edubot.data.models.questions import Questions
from edubot.data.models.resources import Resources
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.students import Students
from edubot.data.models.personalized_ova import PersonalizedOVA, PersonalizedOVAItem


@pytest.fixture()
def with_second_competency(seeded_db):
    """Competência 2 com uma questão própria — para testar o filtro cross-comp."""
    Competencies.create(competency_id=2, competency_description="Comp B", subject_id=1)
    Questions.create(question_id=3, statement="x",
                     alternatives={"alternatives": ["1", "2"]}, answer="a",
                     ova_id=1, competency_id=2)
    return seeded_db


def test_create_personalized_ova_201(client, auth):
    # Base seed: competência 1 tem as questões 1 e 2. O agente mock diagnostica a
    # competência fraca e monta a OVA com as questões de reforço.
    r = client.post("/edubot/personalized-ova", headers=auth(1))
    assert r.status_code == 201
    body = json.loads(r.data.decode())
    assert body["itens_questoes"] >= 1
    assert body["mock"] is True


def test_personalized_ova_owner_only_404(client, auth):
    created = json.loads(client.post("/edubot/personalized-ova", headers=auth(1)).data.decode())
    pid = created["personalized_ova_id"]
    # dono (1) acessa; outro aluno (2) recebe 404 (não vaza existência)
    assert client.get(f"/personalized-ova/{pid}", headers=auth(1)).status_code == 200
    assert client.get(f"/personalized-ova/{pid}", headers=auth(2)).status_code == 404


def test_tool_filters_invented_and_cross_competency_ids(with_second_competency):
    student = Students.get_by_id(1)
    ctx = {"student": student}
    # target = competência 1 (questões 1,2). Passamos: 1 (válida), 3 (é da comp 2),
    # 999 (inexistente). Só a 1 deve persistir.
    result = criar_ova_personalizada(
        ctx, target_competency_id=1, titulo="R", mensagem_aluno="m",
        justificativa="j", resource_ids=[], question_ids=[1, 3, 999])
    assert "personalized_ova_id" in result
    kinds = list(PersonalizedOVAItem
                 .select()
                 .where(PersonalizedOVAItem.personalized_ova_id == result["personalized_ova_id"]))
    qids = [it.question_id for it in kinds if it.item_kind == "question"]
    assert qids == [1]  # 3 (outra comp) e 999 (inexistente) filtradas


def test_tool_errors_without_valid_content(seeded_db):
    student = Students.get_by_id(1)
    result = criar_ova_personalizada(
        {"student": student}, target_competency_id=1, titulo="R",
        mensagem_aluno="m", justificativa="j", resource_ids=[999], question_ids=[999])
    assert "error" in result


# --- P.2 (Plano 2): reforço montado no formato preferido do aluno -----------
def _seed_preference_video(sid=1):
    """Aluno com preferência confiável por vídeo (3 vídeos concluídos) + 1 texto,
    todos na competência 1."""
    Resources.create(resource_id=60, ova_id=1, resource_type="texto",
                     resource_title="texto A", competency_id=1)
    for rid in (61, 62, 63):
        Resources.create(resource_id=rid, ova_id=1, resource_type="video",
                         resource_title=f"video {rid}", competency_id=1)
        ResourceProgress.create(student_id=sid, resource_id=rid,
                                perc_consumed=100, seconds_consumed=0, completed=True)


def test_remediacao_orders_preferred_format_first(seeded_db):
    _seed_preference_video()
    ctx = {"student": Students.get_by_id(1)}
    out = listar_recursos_remediacao(ctx, competency_id=1)
    assert out["formato_preferido_do_aluno"] == "video"
    # o 1º recurso da lista é do formato preferido (a trilha começa por ele)
    assert out["recursos"][0]["tipo"] == "video"


def test_personalized_ova_starts_with_preferred_format(client, auth, seeded_db):
    _seed_preference_video()
    r = client.post("/edubot/personalized-ova", headers=auth(1))
    assert r.status_code == 201
    body = json.loads(r.data.decode())
    assert body["formato_preferido"] == "video"
    # o 1º item-recurso persistido é o vídeo (position 0)
    pova = PersonalizedOVA.get(PersonalizedOVA.student_id == 1)
    first = (PersonalizedOVAItem
             .select()
             .where((PersonalizedOVAItem.personalized_ova_id == pova) &
                    (PersonalizedOVAItem.item_kind == "resource"))
             .order_by(PersonalizedOVAItem.position)
             .first())
    assert Resources.get_by_id(first.resource_id).resource_type == "video"


def test_remediacao_no_preference_keeps_db_order(seeded_db):
    # sem sinal de conclusão -> sem preferência -> ordem do banco preservada
    Resources.create(resource_id=70, ova_id=1, resource_type="texto",
                     resource_title="t", competency_id=1)
    Resources.create(resource_id=71, ova_id=1, resource_type="video",
                     resource_title="v", competency_id=1)
    ctx = {"student": Students.get_by_id(1)}
    out = listar_recursos_remediacao(ctx, competency_id=1)
    assert out["formato_preferido_do_aluno"] is None
    assert [r["resource_id"] for r in out["recursos"]] == [70, 71]
