from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.competencies import Competencies
from peewee import *
import datetime


# B.5 — override de dificuldade por (aluno, competência). Quando presente, o pool
# de /question/ova usa este nível em vez do teto derivado do domínio (D.4). É o
# efeito real da tool `ajustar_dificuldade` (teto de 1 mudança/dia na tool).
class StudentDifficulty(BaseModel):
    student_id = ForeignKeyField(Students, backref="difficulty",
                                 on_delete="cascade", on_update="cascade")
    competency_id = ForeignKeyField(Competencies, backref="difficulty",
                                    on_delete="cascade", on_update="cascade")
    level = IntegerField(default=2)   # 1 fácil · 2 média · 3 difícil
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "student_difficulty"
        primary_key = CompositeKey("student_id", "competency_id")
