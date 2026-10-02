from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *


# G.3 (Plano 2) — sequência de dias de estudo, com "escudo" semanal (1 folga não
# quebra a chama). Perder a sequência ZERA current_days, nunca tira XP já ganho
# (princípio: nada de punição). best_days guarda o recorde.
class StudentStreak(BaseModel):
    student_id = ForeignKeyField(Students, primary_key=True, backref="streak",
                                 on_delete="cascade", on_update="cascade")
    current_days = IntegerField(default=0)
    best_days = IntegerField(default=0)
    last_activity_date = DateField(null=True)
    shield_used_on = DateField(null=True)   # 1 escudo por semana ISO

    class Meta:
        table_name = "student_streak"
