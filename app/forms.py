from wtforms import Form, BooleanField, StringField, DateTimeField, validators
from wtforms.fields.html5 import DateTimeLocalField

class TaskForm(Form):
    name = StringField('Task name', [validators.Length(min=4, max=125), validators.DataRequired()])
    deadline = DateTimeLocalField('Deadline', [validators.DataRequired()], format='%Y-%m-%dT%H:%M')
    accept_tos = BooleanField('Everything is OK', [validators.DataRequired()])

