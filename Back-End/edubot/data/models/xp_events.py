from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *


# G.1 (Plano 2) — trilha de XP server-side. Fonte da verdade do total de XP e do
# ranking semanal. O XP mede ESFORÇO (concluir módulo, revisar em dia, voltar a
# estudar), nunca a nota. Anti-farm: a unique (aluno, regra, objeto, dia) dedup o
# mesmo ganho no mesmo dia; regras com teto diário são limitadas no serviço
# (services/gamification.award).
class XpEvents(BaseModel):
    xp_event_id = AutoField()
    student_id = ForeignKeyField(Students, backref="xp_events",
                                 on_delete="cascade", on_update="cascade")
    rule = CharField(max_length=40)
    object_type = CharField(max_length=20, null=True)
    object_id = IntegerField(null=True)
    points = IntegerField()
    awarded_on = DateField()
    created_at = DateTimeField()

    class Meta:
        table_name = "xp_events"
        indexes = (
            (("student_id", "rule", "object_type", "object_id", "awarded_on"), True),
        )
