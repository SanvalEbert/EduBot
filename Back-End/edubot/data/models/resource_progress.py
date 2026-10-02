from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.resources import Resources
from peewee import *
import datetime


# MELHORIA (4.1): per-student consumption of an individual resource.
# - video:   perc_consumed = % watched, completed when it reaches ~90%
# - podcast: seconds_consumed = listening time, perc_consumed derived from duration
# - atividade: completed set explicitly by the student ("Concluir" button)
# One row per (student, resource), upserted by POST /progress/resource.
class ResourceProgress(BaseModel):
    resource_progress_id = AutoField()
    student_id = ForeignKeyField(Students, backref="resource_progress", on_delete="cascade", on_update="cascade")
    resource_id = ForeignKeyField(Resources, backref="progress", on_delete="cascade", on_update="cascade")
    perc_consumed = IntegerField(default=0)      # 0-100
    seconds_consumed = IntegerField(default=0)   # listening/watching time in seconds
    completed = BooleanField(default=False)
    last_access = DateTimeField(default=datetime.datetime.now)

    # Fase 1 do Plano de Rastreabilidade (migration_019) — consumo REAL de vídeo.
    # `perc_consumed` acima é posição máxima (legado, mantido); o que mede
    # aprendizado de fato é a dupla watched_seconds (tempo assistido) +
    # coverage_perc (quanto da linha do tempo foi realmente percorrida).
    watched_seconds = IntegerField(default=0)          # segundos tocando, aba visível
    coverage_bitmap = CharField(max_length=100, null=True)  # 100 baldes '0'/'1'
    coverage_perc = IntegerField(default=0)            # baldes marcados (0..100)
    last_position_seconds = IntegerField(null=True)    # onde parou (abandono)
    max_position_seconds = IntegerField(null=True)     # ponto mais avançado
    playback_rate_last = FloatField(null=True)         # última velocidade

    class Meta:
        # Nome explícito: o default do Peewee seria "resourceprogress", mas o
        # DDL (ddl_extra.sql) cria "resource_progress"
        table_name = "resource_progress"
        indexes = (
            (("student_id", "resource_id"), True),  # unique pair
        )
