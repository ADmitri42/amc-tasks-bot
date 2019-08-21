from datetime import datetime, timedelta
from pymongo import MongoClient
import telebot
from time import sleep

import config


client = MongoClient(config.dbstring)
db = client.AMCtasks

bot = telebot.TeleBot(config.token)

tasks = db.tasks.find(
            {
                'deadline':
                    {
                        '$lt': datetime.now()+timedelta(0, 60*30)
                    },
                'executor':
                    {
                        '$exists': True
                    },
                'done': False
            }
)

for task in tasks:
    bot.send_message(task['executor'], "It's friendly reminder that you have a task.")
    db.users.update({'chat_id': task['executor']}, {"$set": {'state': 1}})
    sleep(2)
