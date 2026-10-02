from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *
from playhouse.mysql_ext import JSONField
import datetime


# D.1 — evento de aprendizado (xAPI-lite): uma linha por sinal discreto de
# estudo. Verbo + tipo de objeto + id + contexto JSON. É a matéria-prima do
# mastery (D.2), da personalização e da auditoria; substitui gradualmente a
# tabela `interactions` (strings PT livres) por um schema enumerado e agregável.
class LearningEvents(BaseModel):
    event_id = BigAutoField()
    student_id = ForeignKeyField(Students, backref="learning_events",
                                 on_delete="cascade", on_update="cascade")
    verb = CharField(max_length=30)          # ver VERBS em services/events.py
    object_type = CharField(max_length=20)   # ova|resource|question|intervention|session
    object_id = IntegerField(null=True)
    context = JSONField(null=True)           # {perc, seconds, correct, response_ms, text...}
    occurred_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "learning_events"
