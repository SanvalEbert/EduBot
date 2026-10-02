from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.questions import Questions
from peewee import *
import datetime


class Attempts(BaseModel):
    attempt_id = IntegerField(primary_key=True)
    student_id = ForeignKeyField(Students, backref="attempts", on_delete="cascade", on_update="cascade")
    question_id = ForeignKeyField(Questions, backref="attempts", on_delete="cascade", on_update="cascade")
    is_correct = BooleanField()
    attempt_time = DateTimeField(default=datetime.datetime.now)
