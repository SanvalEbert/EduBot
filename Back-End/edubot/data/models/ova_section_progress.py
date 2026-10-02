from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.ovas import OVAs
from peewee import *
import datetime


# Plano de Rastreabilidade — Fase 2 (migration_020): leitura por SEÇÃO do OVA.
# Uma linha por (aluno, OVA, seção), atualizada por POST /progress/ova-section
# somando deltas. É o que permite responder "em que parte do conteúdo o aluno
# travou?" — o rastreio anterior só sabia o total do OVA.
class OVASectionProgress(BaseModel):
    section_progress_id = AutoField()
    student_id = ForeignKeyField(Students, backref="section_progress", on_delete="cascade", on_update="cascade")
    ova_id = ForeignKeyField(OVAs, backref="section_progress", on_delete="cascade", on_update="cascade")
    section_id = CharField(max_length=120)     # id da seção no HTML do OVA
    section_index = IntegerField(default=0)    # ordem de leitura
    active_seconds = IntegerField(default=0)   # tempo ativo (mesmo gate da leitura)
    max_scroll_perc = IntegerField(default=0)  # marca d'água
    visits = IntegerField(default=0)           # > 1 => releitura
    last_access = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "ova_section_progress"
        indexes = (
            (("student_id", "ova_id", "section_id"), True),  # unique
        )
