import logging
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from pymongo import MongoClient
import telebot

import config

logger = logging.getLogger('AMC_tasks_bot')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('tasks_bot.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(chat)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)


client = MongoClient("mongodb+srv://admin:test1@amctasks-3lcps.gcp.mongodb.net/test?retryWrites=true&w=majority")
db = client.AMCtasks

bot = telebot.TeleBot(config.token)


def create_or_find(chat_id):
    user = db.users.find_one({"chat_id": chat_id})
    if user is None:
        chat = bot.get_chat(chat_id)
        user = {
            "chat_id": chat_id,
            "state": 0,
            "username": chat.username
        }
        db.users.insert_one(user)
        user = db.users.find_one({"chat_id": chat_id})

    return user


def send_task(chat_id,
              task_id: ObjectId,
              select_button=False,
              done_button=False,
              yn_button=False,
              message_id=None):
    """
    Send formatted task to user
    :param chat_id:
    :param task_id:
    :param select_button:
    :param done_button:
    :param yn_button:
    :return:
    """
    task = db.tasks.find_one({"_id": task_id})
    if task is None:
        raise ValueError("Id {} not exists".format(task_id))

    keyboard = None
    message = "*{}*\n{}"
    if select_button or done_button or yn_button:
        keyboard = telebot.types.InlineKeyboardMarkup()

        if select_button:
            callback_button = telebot.types.InlineKeyboardButton(text="select", callback_data="select_" + str(task_id))
            keyboard.add(callback_button)

        elif done_button:
            message = "*{}*\n{}\n\n_Done_?"
            callback_button = telebot.types.InlineKeyboardButton(text="done", callback_data="done_" + str(task_id))
            keyboard.add(callback_button)

        elif yn_button:
            callback_button = telebot.types.InlineKeyboardButton(text="Yes", callback_data="done_y_" + str(task_id))
            keyboard.add(callback_button)
            callback_button = telebot.types.InlineKeyboardButton(text="No", callback_data="done_n_" + str(task_id))
            keyboard.add(callback_button)

            message = "*{}*\n{}\n\n*You sure?*"

    if message_id:
        bot.edit_message_text(chat_id=chat_id,
                                  message_id=message_id,
                                  reply_markup=keyboard,
                                  text=message.format(task["name"], task["deadline"]),
                                  parse_mode="Markdown")
    else:
        bot.send_message(chat_id,
                     message.format(task["name"], task["deadline"]),
                     reply_markup=keyboard,
                     parse_mode="Markdown")


def send_active_tasks(chat_id):
    """
    Send list of tasks to user
    :param chat_id:
    :return:
    """
    tasks = db.tasks.find({
        "$and": [{"deadline": {
                    "$gte": datetime.now(),
                    "$lt": datetime.now() + timedelta(0, 3600*8)
                    }}, {"executor": {"$exists": False}}]
                })
    printed = False
    for task in tasks:
        printed = True
        send_task(chat_id, task["_id"], select_button=True)

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
    logger.info("New user", extra={"chat": message.chat.id})
    create_or_find(message.chat.id)
    bot.send_message(message.chat.id, "Hello! Welcome to AMC Tasks")


@bot.message_handler(commands=['tasks'])
def list_of_tasks(message):
    logger.info("Sending list of tasks", extra={"chat": message.chat.id})
    user = create_or_find(message.chat.id)
    if user["state"] == 0:
        send_active_tasks(message.chat.id)
    elif user["state"] == 1 or user["state"] == 2:
        task = db.tasks.find_one({"$and": [{"executor": message.chat.id}, {"done": False}]})
        if task is None:
            db.users.update_one({"chat_id": message.chat.id}, {"$set": {"state": 0}})
            send_active_tasks(message.chat.id)
        else:
            bot.send_message(message.chat.id, "You have active tasks")
            send_task(message.chat.id, task["_id"], False, True)
            if user["state"] == 2:
                db.users.update_one({"chat_id": message.chat.id}, {"$set": {"state": 1}})


@bot.callback_query_handler(func=lambda call: call.data.startswith("select"))
def select_task(call):
    """
    Handler for button select
    :param call:
    :return:
    """
    logging.info("Select button was pushed", extra={"chat": call.message.chat.id})
    if datetime.now() - datetime.utcfromtimestamp(call.message.date) > timedelta(0, 3600*6): # Problem with timezone
        logging.debug("Info is too old", extra={"chat": call.message.chat.id})
        text = "Sorry, but this information is too old.\nGet new list via /tasks."
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text)
        bot.send_message(call.message.chat.id, text)
    elif db.tasks.find_one({"$and": [{"executor": call.message.chat.id}, {"done": False}]}) is not None:
        logging.debug("Already have a task", extra={"chat": call.message.chat.id})
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text="You already have a task.")
    else:
        task_id = call.data.split("_")[-1]
        task = db.tasks.find_one({"_id": ObjectId(task_id)})
        if task:
            logging.debug("Select task" + str(task), extra={"chat": call.message.chat.id})
            if task.get("executor"):
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text="Someone took this task before you. Choose another task.")
            else:
                db.tasks.update_one({"_id": task["_id"]}, {"$set": {"executor": call.message.chat.id}})
                db.users.update_one({"chat_id": call.message.chat.id}, {"$set": {"state": 1}})

                name = ''
                if call.message.chat.first_name:
                    name += call.message.chat.first_name
                if call.message.chat.last_name:
                    name += ' ' + call.message.chat.last_name
                if call.message.chat.username:
                    name += '(@' + call.message.chat.username + ')'

                bot.send_message("@amctasks", "{} took task \"{}\"".format(name, task['name']))
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text="*{}*\n{}\n\n*Your task*".format(task["name"], task["deadline"]),
                                      parse_mode="Markdown")
        else:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text="Something went wrong.\nUpdate list of the tasks via /tasks")


@bot.callback_query_handler(func=lambda call: call.data.startswith("done"))
def done_task(call):
    """
    Handler for button done
    :param call:
    :return:
    """

    logging.info("Done or yes/no button were pushed by user {}".format(call.message.chat.id))
    if datetime.now() - datetime.utcfromtimestamp(call.message.date) > timedelta(0, 3600*3.5):  # Problem with timezone
        text = "Sorry, but this information is too old.\nUpdate it via /tasks."
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text)
        bot.send_message(call.message.chat.id, text)
    else:
        user = create_or_find(call.message.chat.id)
        if user["state"] == 1:
            task_id = call.data.split("_")[-1]
            task = db.tasks.find_one({"_id": ObjectId(task_id)})
            if task:
                db.users.update_one({"chat_id": call.message.chat.id}, {"$set": {"state": 2}})
                send_task(call.message.chat.id,
                          task["_id"],
                          yn_button=True,
                          message_id=call.message.message_id)

            else:
                db.users.update_one({"chat_id": call.message.chat.id}, {"$set": {"state": 0}})
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text="Something went wrong.\nUpdate list of the tasks via /tasks")
        elif user["state"] == 2:
            task_id = call.data.split("_")[-1]
            sol = call.data.split("_")[1]
            task = db.tasks.find_one({"_id": ObjectId(task_id)})
            if task:
                if sol == "y":
                    db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"done": True}})
                    db.users.update_one({"chat_id": call.message.chat.id}, {"$set": {"state": 0}})

                    name = ''
                    if call.message.chat.first_name:
                        name += call.message.chat.first_name
                    if call.message.chat.last_name:
                        name += ' ' + call.message.chat.last_name
                    if call.message.chat.username:
                        name += '(@' + call.message.chat.username + ')'

                    bot.send_message("@amctasks",
                                     "Task \"{}\" done by {}".format(task['name'], name))
                    bot.edit_message_text(chat_id=call.message.chat.id,
                                          message_id=call.message.message_id,
                                          text="*{}*\n{}\n\n*Done*".format(task["name"], task["deadline"]),
                                          parse_mode="Markdown")
                elif sol == "n":
                    db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"done": False}})
                    db.users.update_one({"chat_id": call.message.chat.id}, {"$set": {"state": 1}})
                    bot.edit_message_text(chat_id=call.message.chat.id,
                                          message_id=call.message.message_id,
                                          text="*{}*\n{}\n\n*Your task*".format(task["name"], task["deadline"]),
                                          parse_mode="Markdown")


if __name__ == '__main__':
    bot.send_message("@amctasks",
                    "*Bot enabled*",
                    parse_mode="Markdown")
    for _ in range(3):
        logger.info("Bot started", extra={"chat": "Not chat"})
        try:
            bot.polling(none_stop=True)
        except telebot.apihelper.ApiExceptionKeyboardInterrupt as e:
            logging.error("Exception", exc_info=True)
    bot.send_message("@amctasks",
                    "*Bot is disabled*",
                    parse_mode="Markdown")
