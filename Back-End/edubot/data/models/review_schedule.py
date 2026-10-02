from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.competencies import Competencies
from peewee import *
import datetime


# D.3 — agenda de revisão espaçada (SM-2 simplificado) por (aluno, competência).
# `interval_days` cresce a cada revisão bem-sucedida (× ease, teto REVIEW_MAX);
# um erro reseta para 1 dia e reduz o `ease`. `status` acompanha o ciclo de vida.
class ReviewSchedule(BaseModel):
    review_id = AutoField()
    student_id = ForeignKeyField(Students, backref="reviews",
                                 on_delete="cascade", on_update="cascade")
    competency_id = ForeignKeyField(Competencies, backref="reviews",
                                    on_delete="cascade", on_update="cascade")
    due_date = DateField()
    interval_days = IntegerField(default=1)
    ease = FloatField(default=2.5)
    status = CharField(max_length=20, default="agendada")  # agendada|vencida|cumprida|cancelada
    created_by = CharField(max_length=20, default="agent")  # agent|rule|tutor
    created_at = DateTimeField(default=datetime.datetime.now, null=True)

    class Meta:
        table_name = "review_schedule"
        indexes = ((("student_id", "competency_id", "due_date"), True),)  # uc_review
