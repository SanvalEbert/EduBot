"""P.1 (Plano 2) — serviço de preferência de aprendizagem."""
import datetime

from edubot.data.models.agent_decisions import AgentDecisions
from edubot.data.models.attempts import Attempts
from edubot.data.models.questions import Questions
from edubot.data.models.resources import Resources
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.students import Students
from edubot.services import preferences
from edubot.services.student_context import build_student_profile


def _resource(rid, rtype, competency_id=1):
    return Resources.create(resource_id=rid, ova_id=1, resource_type=rtype,
                            resource_title=f"{rtype}-{rid}", competency_id=competency_id)


def _progress(sid, rid, completed=False, perc=0):
    ResourceProgress.create(student_id=sid, resource_id=rid,
                            perc_consumed=perc, seconds_consumed=0, completed=completed)


def test_prefers_format_with_higher_completion(seeded_db):
    # 3 vídeos concluídos, 3 textos abandonados -> formato = video, confiante.
    for rid in (10, 11, 12):
        _resource(rid, "video")
        _progress(1, rid, completed=True)
    for rid in (20, 21, 22):
        _resource(rid, "texto")
        _progress(1, rid, completed=False, perc=10)

    profile = build_student_profile(Students.get_by_id(1))
    pref = preferences.learning_preference(1, profile)
    assert pref["formato"] == "video"
    assert pref["confianca"] >= 0.5
    assert pref["taxa_conclusao_por_formato"]["video"] == 1.0
    assert preferences.preferred_format(1, profile) == "video"


def test_no_signal_means_no_preference(seeded_db):
    # aluno sem consumo -> sem preferência, confiança 0 (degradação segura).
    pref = preferences.learning_preference(2)
    assert pref["formato"] is None
    assert pref["confianca"] == 0.0
    assert preferences.preferred_format(2) is None


def test_weak_signal_below_confidence_threshold(seeded_db):
    # 1 única conclusão -> confianca 0.25 < 0.4 -> preferred_format devolve None
    _resource(30, "podcast")
    _progress(1, 30, completed=True)
    profile = build_student_profile(Students.get_by_id(1))
    pref = preferences.learning_preference(1, profile)
    assert pref["confianca"] < preferences.CONFIDENT
    assert preferences.preferred_format(1, profile) is None


def test_responded_best_to_intervention_format(seeded_db):
    now = datetime.datetime.now()
    # sugestão em vídeo -> aceita; sugestão em texto -> dispensada
    AgentDecisions.create(student_id=1, trigger_type="sweep",
                          input_digest={"formato_sugerido": "video"},
                          mock=True, outcome="aceita", created_at=now)
    AgentDecisions.create(student_id=1, trigger_type="sweep",
                          input_digest={"formato_sugerido": "texto"},
                          mock=True, outcome="dispensada", created_at=now)
    fmt, taxa = preferences._best_intervention_format(1)
    assert fmt == "video" and taxa == 1.0


def test_comfortable_difficulty(seeded_db):
    # nível 1 tem 2 acertos/2; nível 3 tem 0/2 -> confortável = 1
    Questions.create(question_id=101, statement="facil", answer="a",
                     alternatives={"alternatives": ["a", "b"]}, ova_id=1,
                     competency_id=1, difficulty=1)
    Questions.create(question_id=103, statement="dificil", answer="a",
                     alternatives={"alternatives": ["a", "b"]}, ova_id=1,
                     competency_id=1, difficulty=3)
    for _ in range(2):
        Attempts.create(student_id=1, question_id=101, is_correct=True)
        Attempts.create(student_id=1, question_id=103, is_correct=False)
    assert preferences._comfortable_difficulty(1) == 1
