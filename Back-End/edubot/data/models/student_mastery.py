from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.competencies import Competencies
from peewee import *
import datetime


# D.2 — modelo do aluno por competência (Bayesian Knowledge Tracing).
# p_mastery = probabilidade estimada de o aluno dominar a competência, atualizada
# a cada tentativa e com decaimento por tempo sem prática (services/mastery.py).
# Chave composta (student_id, competency_id): uma linha por par.
class StudentMastery(BaseModel):
    student_id = ForeignKeyField(Students, backref="mastery",
                                 on_delete="cascade", on_update="cascade")
    competency_id = ForeignKeyField(Competencies, backref="mastery",
                                    on_delete="cascade", on_update="cascade")
    p_mastery = FloatField(default=0.2)
    attempts_seen = IntegerField(default=0)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "student_mastery"
        primary_key = CompositeKey("student_id", "competency_id")
