# Import the necessary classes
from edubot.data.models.base import BaseModel
from edubot.data.models.courses import Courses
from edubot.data.models.subjects import Subjects
from peewee import *

# Association table that links courses with subjects

# This table allows a course to include multiple subjects
# and a subject to be offered in multiple courses
class Offerings(BaseModel):
    # Unique identifier for the association table
    offering_id = IntegerField(primary_key=True)
    # Foreign key referencing the course
    course_id = ForeignKeyField(Courses, backref="offerings", on_delete="cascade", on_update="cascade")
    # Foreign key referencing the subject
    subject_id = ForeignKeyField(Subjects, backref="offerings", on_delete="cascade", on_update="cascade")
