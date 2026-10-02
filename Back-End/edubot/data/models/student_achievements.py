from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *


# G.2 (Plano 2) — conquistas desbloqueadas pelo aluno. O CATÁLOGO (nome, critério,
# recompensa) vive no código (services/gamification.ACHIEVEMENTS); aqui fica só o
# registro do que cada aluno já desbloqueou (chave composta = idempotente).
class StudentAchievements(BaseModel):
    student_id = ForeignKeyField(Students, backref="achievements",
                                 on_delete="cascade", on_update="cascade")
    achievement_id = CharField(max_length=40)
    unlocked_at = DateTimeField()

    class Meta:
        table_name = "student_achievements"
        primary_key = CompositeKey("student_id", "achievement_id")
