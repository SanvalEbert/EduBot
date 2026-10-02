from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *


# E.3 (Plano 2) — meta semanal do aluno. O EduBot sugere; o aluno aceita; o
# progresso vem dos MESMOS sinais do XP (sem telemetria nova). Uma por
# (aluno, semana, tipo) — o unique dá idempotência à sugestão do sweep.
class WeeklyGoals(BaseModel):
    goal_id = AutoField()
    student_id = ForeignKeyField(Students, backref="weekly_goals",
                                 on_delete="cascade", on_update="cascade")
    week_start = DateField()
    kind = CharField(max_length=30)     # dias_de_estudo|concluir_modulos|revisoes_em_dia
    target = IntegerField()
    progress = IntegerField(default=0)
    status = CharField(max_length=20, default="sugerida")  # sugerida|aceita|cumprida|expirada
    created_at = DateTimeField()

    class Meta:
        table_name = "weekly_goals"
        indexes = (
            (("student_id", "week_start", "kind"), True),
        )
