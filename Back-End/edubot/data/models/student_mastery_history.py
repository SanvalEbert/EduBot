from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.competencies import Competencies
from peewee import *


# H.1 (Plano 2) — snapshot diário do domínio (p_mastery) por competência.
# O sweep diário grava uma linha por (aluno, competência, dia); o serviço
# mastery.mastery_trend deriva a tendência de 7 dias (setas na teia — G.5).
# Chave composta (student, competency, data) dá idempotência ao snapshot.
class StudentMasteryHistory(BaseModel):
    student_id = ForeignKeyField(Students, backref="mastery_history",
                                 on_delete="cascade", on_update="cascade")
    competency_id = ForeignKeyField(Competencies, backref="mastery_history",
                                    on_delete="cascade", on_update="cascade")
    snapshot_date = DateField()
    p_mastery = FloatField()

    class Meta:
        table_name = "student_mastery_history"
        primary_key = CompositeKey("student_id", "competency_id", "snapshot_date")
