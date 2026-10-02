from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.ovas import OVAs
from peewee import *


class OVAProgress(BaseModel):
    progress_id = IntegerField(primary_key=True)
    student_id = ForeignKeyField(Students, backref="ova_progress", on_delete="cascade", on_update="cascade")
    ova_id = ForeignKeyField(OVAs, backref="ova_progress", on_delete="cascade", on_update="cascade")
    read_time = IntegerField(null=True)  # seconds
    perc_scrolled = IntegerField(null=True)  # 0-100
    completed = BooleanField(default=False)
    last_access = DateTimeField(null=True)

    class Meta:
        # BUGFIX: sem isso o Peewee procura a tabela "ovaprogress", mas o DDL
        # (ddl_extra.sql) cria "ova_progress" — quebrava só no MySQL, pois no
        # fallback SQLite as tabelas eram criadas pelo próprio Peewee.
        table_name = "ova_progress"
