from datetime import datetime
from pymongo import MongoClient
from pandas import read_csv

import config

client = MongoClient(config.dbstring)
db = client.AMCtasks

filename = str(input("filename: "))
if not filename.endswith(".csv"):
    raise ValueError("Must be csv file")

tasks_df = read_csv(filename, sep=';', header=0)
tasks = []
# print(tasks_df.head())
for task in tasks_df.iterrows():
    task = {'name': task[1]['name'], 'deadline': datetime.strptime(task[1].deadline, '%d.%m.%Y %H:%M'), 'done': False}
    tasks.append(task)
#
print("Please, check that everything is ok")
for task in tasks:
    print("{}\n\t{}".format(task['name'], task['deadline']))

if str(input("Is it fine?(y/n)")) == 'y':
    db.tasks.insert_many(tasks)
print("Done")
