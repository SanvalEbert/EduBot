

# Import necessary libraries
from flask import Blueprint, request
from flask_cors import cross_origin
from peewee import PeeweeException # ORM library
import json
from collections import defaultdict

# Import ORM classes used in the routes
from edubot.data.models.offerings import Offerings
from edubot.data.models.subjects import Subjects
from edubot.data.models.ovas import OVAs

# Create a route blueprint as a reusable component
app_ova = Blueprint("ova", __name__)

# Given a course, return all the OVAs associated with that course
@app_ova.route("/ova/course/<int:course_id>", methods=["GET"])
# Enable cross-origin requests from other domains
@cross_origin()
def show_course_OVAs(course_id):
    if request.method == "GET":
        try:
            # Create aliases for less verbose queries
            of = Offerings.alias()
            s = Subjects.alias()
            o = OVAs.alias()
            
            # Query all OVAs for the specified course, joining the tables by their IDs and filtering by course ID
            query = o.select(s.subject_id, s.subject_name, o.ova_id, o.ova_name, o.link).join(s).join(of).where(of.course_id == course_id)
            
            # Initialize a defaultdict to handle missing keys automatically
            result = defaultdict(lambda: {"subject_id": -1, "ovas": []})
            
            # For each OVA, append the ID, name, and link to the result
            for ova in query:
                subject = ova.subject_id
                if result[subject.subject_name]["subject_id"] == -1:
                    result[subject.subject_name]["subject_id"] = subject.subject_id
                result[subject.subject_name]["ovas"].append({
                    "ova_id": ova.ova_id,
                    "ova_name": ova.ova_name,
                    "link": ova.link
                })
            return json.dumps(result)
        # Handle errors and return the error description
        except PeeweeException as err:
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return a message if the HTTP method is not GET
        return "Wrong Request Methods. Only GET Allowed", 405

# Return all OVAs associated with a specific subject
@app_ova.route("/ova/subject/<int:subject_id>", methods=["GET"])
@cross_origin()
def show_subject_OVAs(subject_id):
    if request.method == "GET":
        try:
            # Retrieve all OVAs for the specified subject
            ovas = OVAs.select().where(OVAs.subject_id == subject_id)
            ova_list = []
            # For each OVA, append its ID and name to the list
            for ova in ovas:
                ova_dict = {
                    "ova_id": ova.ova_id,
                    "ova_name": ova.ova_name
                }
                ova_list.append(ova_dict.copy())
            # Return the resulting array
            return json.dumps(ova_list)
        except PeeweeException as err:
            # Handle errors and return the error description
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return a message if the HTTP method is not GET
        return "Wrong Request Methods. Only GET Allowed", 405
