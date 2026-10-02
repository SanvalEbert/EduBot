"""A2/A15 — perfil do aluno (fonte única) e inatividade multi-sinal."""
import datetime

from edubot.data.models.students import Students
from edubot.data.models.attempts import Attempts
from edubot.data.models.ova_progress import OVAProgress
from edubot.services.student_context import build_student_profile, _days_without_access


def test_profile_has_expected_shape(seeded_db):
    prof = build_student_profile(Students.get_by_id(1))
    for key in ("estudante", "dias_sem_acesso", "recursos", "quiz",
                "atividades_pendentes", "ovas", "competencias", "historico_intervencoes"):
        assert key in prof
    assert prof["estudante"]["nome"] == "Ana Souza"


def test_inactivity_none_without_any_activity(seeded_db):
    assert _days_without_access(Students.get_by_id(1)) is None


def test_inactivity_from_quiz_attempt_counts(seeded_db):
    # Sem interação em `interactions`, mas com uma tentativa de quiz hoje.
    Attempts.create(student_id=1, question_id=1, is_correct=True,
                    attempt_time=datetime.datetime.now())
    assert _days_without_access(Students.get_by_id(1)) == 0


def test_inactivity_from_reading_access(seeded_db):
    # Só leitura de OVA (last_access), nenhuma outra atividade.
    OVAProgress.create(student_id=1, ova_id=1, read_time=60, perc_scrolled=50,
                       completed=False, last_access=datetime.datetime.now())
    assert _days_without_access(Students.get_by_id(1)) == 0
