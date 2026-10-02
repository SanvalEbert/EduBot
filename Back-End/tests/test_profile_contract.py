"""A.1 — Teste de CONTRATO do perfil do aluno.

Garante que a reescrita de `build_student_profile` (loops N+1 -> agregações SQL)
NÃO altera a saída. Estratégia golden-snapshot: um cenário rico é semeado e o
dict do perfil é comparado, campo a campo, com um snapshot gravado da
implementação de referência (`tests/golden_profile.json`).

Fluxo: rode uma vez com a implementação atual (gera o golden); depois da
reescrita, o mesmo teste deve continuar verde.

Também conta as queries emitidas (A.1 exige perfil enxuto) via um contador
plugado em `db.execute_sql`.
"""
import datetime
import json
import os

import pytest

from edubot.data.models.base import db
from edubot.data.models.competencies import Competencies
from edubot.data.models.ovas import OVAs
from edubot.data.models.resources import Resources
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.questions import Questions
from edubot.data.models.answers import Answers
from edubot.data.models.attempts import Attempts
from edubot.data.models.interventions import Interventions
from edubot.data.models.students import Students
from edubot.services.student_context import build_student_profile

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_profile.json")

# Datas para o snapshot ser estável em QUALQUER dia de execução:
#  - atividade (progresso/attempts) = AGORA  -> dias_sem_acesso == 0 sempre;
#  - intervenções = data FIXA no passado -> historico_intervencoes não muda de
#    um dia para o outro (o golden é comparado literalmente).
TODAY = datetime.date.today()
NOW = datetime.datetime.now()
FIXED_INTERVENTION_DATE = datetime.date(2020, 1, 1)
# last_access de OVA fixo (U.4 expõe no perfil). Estável para o golden; não
# afeta dias_sem_acesso, cujo MAX é dominado pelos attempts em NOW.
FIXED_OVA_ACCESS = datetime.datetime(2020, 1, 1, 12, 0, 0)


@pytest.fixture()
def rich_seed(seeded_db):
    """Cenário completo sobre o seed base do conftest (aluno 1 = Ana)."""
    Competencies.create(competency_id=2, competency_description="Comp B", subject_id=1)
    OVAs.create(ova_id=2, ova_name="OVA 2", subject_id=1, num_interactions=0, link="b.html")

    # Recursos variados (exercita cada ramo de _resource_state)
    Resources.create(resource_id=1, ova_id=1, resource_type="texto",
                     resource_title="Texto A", competency_id=1)
    Resources.create(resource_id=2, ova_id=1, resource_type="video",
                     resource_title="Video A", competency_id=1, duration_seconds=100)
    Resources.create(resource_id=3, ova_id=1, resource_type="podcast",
                     resource_title="Podcast A", competency_id=2, duration_seconds=200)
    Resources.create(resource_id=4, ova_id=1, resource_type="atividade",
                     resource_title="Atividade A", competency_id=2)
    Resources.create(resource_id=5, ova_id=1, resource_type="quiz",
                     resource_title="Quiz A", competency_id=1)
    Resources.create(resource_id=6, ova_id=2, resource_type="video",
                     resource_title="Video B", competency_id=2, duration_seconds=300)

    Questions.create(question_id=3, statement="4+4?",
                     alternatives={"alternatives": ["8", "9"]}, answer="a",
                     ova_id=2, competency_id=2)

    # Progresso de OVA (texto vem daqui). last_access FIXO -> golden estável.
    OVAProgress.create(student_id=1, ova_id=1, read_time=120, perc_scrolled=95,
                       completed=True, last_access=FIXED_OVA_ACCESS)
    OVAProgress.create(student_id=1, ova_id=2, read_time=30, perc_scrolled=40,
                       completed=False, last_access=FIXED_OVA_ACCESS)

    # Progresso de recursos de mídia
    ResourceProgress.create(student_id=1, resource_id=2, perc_consumed=90,
                            seconds_consumed=90, completed=True, last_access=NOW)
    ResourceProgress.create(student_id=1, resource_id=3, perc_consumed=50,
                            seconds_consumed=100, completed=False, last_access=NOW)
    ResourceProgress.create(student_id=1, resource_id=6, perc_consumed=100,
                            seconds_consumed=0, completed=True, last_access=NOW)

    # Attempts: q1 (acerto+erro), q2 (erro), q3 (acerto)
    Attempts.create(student_id=1, question_id=1, is_correct=True, attempt_time=NOW)
    Attempts.create(student_id=1, question_id=1, is_correct=False, attempt_time=NOW)
    Attempts.create(student_id=1, question_id=2, is_correct=False, attempt_time=NOW)
    Attempts.create(student_id=1, question_id=3, is_correct=True, attempt_time=NOW)

    # Answers (acertos consolidados)
    Answers.create(student_id=1, question_id=1)
    Answers.create(student_id=1, question_id=3)

    # Histórico de intervenções
    Interventions.create(student_id=1, date=FIXED_INTERVENTION_DATE, type="trilha_minima",
                         description="Foque nos essenciais", result="pendente")
    Interventions.create(student_id=1, date=FIXED_INTERVENTION_DATE, type="revisao_alternativa",
                         description="Revise por outro caminho", result="lida")
    return seeded_db


class _QueryCounter:
    """Conta chamadas a db.execute_sql durante o bloco `with`."""
    def __init__(self, database):
        self.database = database
        self.count = 0
        self._orig = None

    def __enter__(self):
        self._orig = self.database.execute_sql

        def _counting(*args, **kwargs):
            self.count += 1
            return self._orig(*args, **kwargs)

        self.database.execute_sql = _counting
        return self

    def __exit__(self, *exc):
        self.database.execute_sql = self._orig


def test_profile_contract_matches_golden(rich_seed):
    profile = build_student_profile(Students.get_by_id(1))
    # normaliza para JSON comparável (datas viram string)
    got = json.loads(json.dumps(profile, default=str, sort_keys=True))

    if not os.path.exists(GOLDEN_PATH):
        with open(GOLDEN_PATH, "w", encoding="utf-8") as fh:
            json.dump(got, fh, ensure_ascii=False, indent=2, sort_keys=True)
        pytest.skip("Golden gerado a partir da implementação atual; rode de novo.")

    with open(GOLDEN_PATH, encoding="utf-8") as fh:
        golden = json.load(fh)
    assert got == golden


def test_profile_query_budget(rich_seed):
    student = Students.get_by_id(1)  # carga do aluno NÃO conta para o perfil
    with _QueryCounter(db) as counter:
        build_student_profile(student)
    # A.1: perfil enxuto. Antes da reescrita eram ~30 queries; a meta da
    # reescrita é <= 8 (agregações). O teste trava regressão do N+1.
    assert counter.count <= 8, f"perfil emitiu {counter.count} queries (meta <= 8)"
