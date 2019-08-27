from flask import render_template, request, redirect, url_for, flash
from app import app
from app.forms import TaskForm
from pymongo import MongoClient
import config
from datetime import datetime

client = MongoClient(config.dbstring)
db = client.AMCtasks

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    form = TaskForm(request.form)
    if request.method == 'POST' and form.validate():
        task = {'name': form.name.data, 'deadline': form.deadline.data, 'done': False}
        db.tasks.insert_one(task)
        return redirect(url_for('done'))
    return render_template('index.html', form=form)


@app.route('/done')
def done():
    return redirect(url_for('index'))

