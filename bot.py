import datetime
from bson.objectid import ObjectId
from pymongo import MongoClient
import telebot

token = "978806256:AAFf0aObxS1zKz1B5VAtxH7LltCGSUK81ws"
client = MongoClient("mongodb+srv://admin:test1@amctasks-3lcps.gcp.mongodb.net/test?retryWrites=true&w=majority")
db = client.AMCtasks

bot = telebot.TeleBot(token)


def create_or_find(chat_id):
    user = db.users.find_one({"chat_id": chat_id})
    if user is None:
        user = {
            "chat_id": chat_id,
                "state": 0}
        db.users.insert_one(user)
        user = db.users.find_one({"chat_id": chat_id})

    return user


def send_task(chat_id, task_id: ObjectId, select_button=True):
    """
    Send formatted task to user
    :param chat_id:
    :param task_id:
    :param select_button:
    :return:
    """
    task = db.tasks.find_one({"_id": task_id})
    if task is None:
        raise ValueError("Id {} not exists".format(task_id))

    keyboard = None
    if select_button:
        keyboard = telebot.types.InlineKeyboardMarkup()
        callback_button = telebot.types.InlineKeyboardButton(text="select", callback_data=str(task_id))
        keyboard.add(callback_button)

    bot.send_message(chat_id, "*{}*\n{}".format(task["name"], task["deadline"]),
                         reply_markup=keyboard, parse_mode="Markdown")


def send_active_tasks(chat_id):
    """
    Send list of tasks to user
    :param chat_id:
    :return:
    """
    tasks = db.tasks.find({
        "$and": [{"deadline": {
                    "$gte": datetime.datetime.now(),
                    "$lt": datetime.datetime.now() + datetime.timedelta(0, 3600*8)
                    }}, {"executor": {"$exists": False}}]
                })
    printed=False
    for task in tasks:
        printed = True
        send_task(chat_id, task["_id"], True)

    if not printed:
        bot.send_message(chat_id, "There is no tasks for you right now")

@bot.message_handler(commands=['start'])
def start(message):
    """
    Create new user in system
    :param message:
    :return:

    states:
        0 - not busy
        1 - busy
        2 - almost done
    """
    create_or_find(message.chat.id)
    bot.send_message(message.chat.id, "Hello! Welcome to AMC Tasks")


@bot.message_handler(commands=['tasks'])
def list_of_tasks(message):
    print("User wants tasks")
    user = create_or_find(message.chat.id)
    if user["state"] == 0:
        send_active_tasks(message.chat.id)
    elif user["state"] == 1:
        task = db.tasks.find_one({"executor": message.chat.id})
        if task is None:
            db.users.update_one({"chat_id": message.chat.id}, {"$set": {"state": 0}})
            send_active_tasks(message.chat.id)
        else:
            bot.send_message(message.chat.id, "You have active tasks")
            send_task(message.task.id, task["_id"], False)


if __name__ == '__main__':
    print("Bot started...")
    bot.polling(none_stop=True)