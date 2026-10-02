from edubot.data.models.base import BaseModel
from edubot.data.models.ovas import OVAs
from edubot.data.models.competencies import Competencies
from peewee import *


# A learning resource that belongs to an OVA.
#
# resource_type defines the pedagogical kind of resource:
#   "texto" | "video" | "podcast" | "quiz" | "atividade"
#
# MELHORIA (4.1): video/podcast support. The pair (resource_url, media_type) is a
# hosting-agnostic abstraction: the URL can point to a self-hosted file (S3,
# local upload served by Apache) or to an external embed (YouTube, Spotify...).
# The players on the frontend receive the raw URL and decide how to render it,
# so the hosting decision can be made later without schema changes.
class Resources(BaseModel):
    resource_id = IntegerField(primary_key=True)
    ova_id = ForeignKeyField(OVAs, backref="resources", on_delete="cascade", on_update="cascade")
    resource_type = CharField(max_length=50)
    resource_title = CharField(max_length=255)
    # Tradução EN (Fase 4 — A12); NULL cai no PT (degradação segura)
    resource_title_en = CharField(max_length=255, null=True)
    # Where the media lives (null for texto/quiz/atividade embedded in the OVA page)
    resource_url = TextField(null=True)
    # How the URL should be interpreted by the player: "upload" (direct file),
    # "youtube", "spotify", ... Extensible without migration (free-form string).
    media_type = CharField(max_length=30, null=True)
    # Duration in seconds (when known) — used to compute consumption percentages
    duration_seconds = IntegerField(null=True)
    # MELHORIA (OVA personalizada): a qual competência este recurso remedia.
    # É o que torna os recursos um "banco pré-selecionado" consultável por
    # assunto: o agente EduBot busca recursos por competency_id para montar a
    # OVA de reforço. Nulo para recursos genéricos do OVA (quiz/atividade) ou
    # ainda não classificados.
    competency_id = ForeignKeyField(Competencies, backref="resources", null=True,
                                     on_delete="set null", on_update="cascade")
