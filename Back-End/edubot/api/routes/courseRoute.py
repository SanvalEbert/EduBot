

# Import necessary libraries
from flask import Blueprint, request
from flask_cors import cross_origin
from peewee import PeeweeException # ORM library
import json

# Import ORM classes used in the routes
from edubot.data.models.courses import Courses
from edubot.data.models.offerings import Offerings
from edubot.data.models.subjects import Subjects

# Create a route blueprint as a reusable component
app_course = Blueprint("course", __name__)

# Define a route to return all courses
@app_course.route("/courses", methods=["GET"])
# Enable cross-origin requests from other domains
@cross_origin()
def get_courses():
    if request.method == "GET":
        try:
            # Retrieve all courses except those restricted to administrators
            courses = Courses.select().where(Courses.course_id < 100)
            course_list = []
            # Iterate over the retrieved courses
            for course in courses:
                # For each course, create a dictionary with course ID and name
                course_dict = {
                    "course_id": course.course_id,
                    "course_name": course.course_name
                }
                course_list.append(course_dict.copy())
            # Return a list of courses as a JSON array
            return json.dumps(course_list)
        # Handle errors and return the error description
        except PeeweeException as err:
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return a message if the HTTP method is not GET
        return "Wrong Request Methods. Only GET Allowed", 405

# Define a route to return all subjects for a specific course ID
@app_course.route("/course/<int:course_id>/subjects", methods=["GET"])
# Enable cross-origin requests from other domains
@cross_origin()
def get_course_subjects(course_id):
    if request.method == "GET":
        try:
            # Aliases for convenience in the query
            s = Subjects.alias()
            of = Offerings.alias()
            
            # Retrieve all subjects associated with the specified course ID
            subjects =  s.select(s.subject_id, s.subject_name).join(of).where(of.course_id == course_id)
            subject_list = []
            
            for subject in subjects:
                # For each subject, create a dictionary with subject ID and name
                subject_dict = {
                    "subject_id": subject.subject_id,
                    "subject_name": subject.subject_name
                }
                subject_list.append(subject_dict.copy())
            # Return a list of subjects as a JSON array
            return json.dumps(subject_list)
        # Handle errors and return the error description
        except PeeweeException as err:
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return a message if the HTTP method is not GET
        return "Wrong Request Methods. Only GET Allowed", 405