# Import the necessary classes
from edubot.data.models.base import BaseModel
from edubot.data.models.courses import Courses
from peewee import *

# Class representing the subjects table
class Subjects(BaseModel):
    # Unique identifier for the subject
    subject_id = IntegerField(primary_key=True)
    # Name of the subject
    subject_name = TextField()
    
    class Meta:
        # Specifies the table name in the database
        table_name = "course_subjects"
