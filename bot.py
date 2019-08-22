import logging
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from pymongo import MongoClient
import telebot

import database
import config

logger = logging.getLogger('AMC_tasks_bot')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('tasks_bot.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(chat)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)


db = database.Database(config.dbstring)
bot = telebot.TeleBot(config.token)


def create_or_find(chat_id):
    user = db.get_user(chat_id)
    if user is None:
        chat = bot.get_chat(chat_id)
        user = db.create_user(chat_id,
                              chat['username'],
                              chat['first_name'],
                              chat['last_name']
                              )
    return user


def send_task(user,
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
    :param message_id:
    :return:
    """
    task = db.get_task(task_id)
    if task is None:
        raise ValueError("Id {} not exists".format(task_id))

    keyboard = None
    message = str(task)
    if select_button or done_button or yn_button:
        keyboard = telebot.types.InlineKeyboardMarkup()

        if select_button:
            callback_button = telebot.types.InlineKeyboardButton(text="select", callback_data="select_" + str(task_id))
            keyboard.add(callback_button)

        elif done_button:
            message += "\n\n_Done_?"
            callback_button = telebot.types.InlineKeyboardButton(text="done", callback_data="done_" + str(task_id))
            keyboard.add(callback_button)

        elif yn_button:
            callback_button = telebot.types.InlineKeyboardButton(text="Yes", callback_data="done_y_" + str(task_id))
            keyboard.add(callback_button)
            callback_button = telebot.types.InlineKeyboardButton(text="No", callback_data="done_n_" + str(task_id))
            keyboard.add(callback_button)

            message += "\n\n*You sure?*"

    if message_id:
        bot.edit_message_text(chat_id=user.chat_id,
                              message_id=message_id,
                              reply_markup=keyboard,
                              text=message,
                              parse_mode="Markdown")
    else:
        bot.send_message(user.chat_id,
                         message,
                         reply_markup=keyboard,
                         parse_mode="Markdown")


def send_active_tasks(user):
    """
    Send list of tasks to user
    :param user:
    :return:
    """
    tasks_id = db.get_active_tasks_id()
    if len(tasks_id) > 0:
        for task_id in tasks_id:
            send_task(user, task_id['_id'], select_button=True)
    else:
        bot.send_message(user.chat_id, "There is no tasks for you right now")


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
    bot.send_message(message.chat.id, config.hellomessage)


@bot.message_handler(commands=['tasks'])
def list_of_tasks(message):
    logger.info("Sending list of tasks", extra={"chat": message.chat.id})
    user = create_or_find(message.chat.id)

    if user.state == database.NOTBUSY:
        send_active_tasks(user)

    elif user.state == 1 or user.state == 2:
        task = db.find_task(user)

        if task is None:
            user.update_state(database.NOTBUSY)
            logger.error("State of user {} but no tasks".format(user["state"]))
            send_active_tasks(user)

        else:
            bot.send_message(user.chat_id, "You have active tasks")
            send_task(user, task.id, False, True)

            if user.state == database.ALMOSTDONE:
                user.update_state(database.BUSY)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select"))
def select_task(call):
    """
    Handler for button select
    :param call:
    :return:
    """
    logging.info("Select button was pushed", extra={"chat": call.message.chat.id})
    user = db.get_user(call.message.chat.id)

    if datetime.now() - datetime.utcfromtimestamp(call.message.date) > timedelta(0, 3600*6): # Problem with timezone
        logging.debug("Info is too old", extra={"chat": call.message.chat.id})
        text = "Sorry, but this information is too old.\nGet new list via /tasks."
        bot.edit_message_text(chat_id=user.chat_id, message_id=call.message.message_id, text=text)
        bot.send_message(user.chat_id, text)

    elif db.find_task(user) is not None:
        logging.debug("You already have a task", extra={"chat": call.message.chat.id})
        bot.edit_message_text(chat_id=user.chat_id,
                              message_id=call.message.message_id,
                              text="You already have a task.")

    else:
        task_id = call.data.split("_")[-1]
        task = db.get_task(ObjectId(task_id))
        if task:
            logging.debug("Select task " + str(task.id), extra={"chat": call.message.chat.id})
            if task.executor:
                bot.edit_message_text(chat_id=user.chat_id,
                                      message_id=call.message.message_id,
                                      text="Someone took this task before you. Choose another task.")
            else:
                task.add_executor(user)
                user.update_state(database.BUSY)

                bot.send_message(config.channelname, "{} took task \"{}\"".format(task, task.name))
                bot.edit_message_text(chat_id=user.chat_id,
                                      message_id=call.message.message_id,
                                      text=str(task) + "\n\n*Your task*",
                                      parse_mode="Markdown")
        else:
            bot.edit_message_text(chat_id=user.chat_id,
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
    user = db.get_user(call.message.chat.id)

    if datetime.now() - datetime.utcfromtimestamp(call.message.date) > timedelta(0, 3600*3.5):  # Problem with timezone
        text = "Sorry, but this information is too old.\nUpdate it via /tasks."
        bot.edit_message_text(chat_id=user.chat_id, message_id=call.message.message_id, text=text)
        bot.send_message(user.chat_id, text)
    else:
        if user.state == database.BUSY:
            task_id = call.data.split("_")[-1]
            task = db.get_task(ObjectId(task_id))
            if task:
                user.update_state(database.ALMOSTDONE)
                send_task(user,
                          task.id,
                          yn_button=True,
                          message_id=call.message.message_id)

            else:
                user.update_state(database.BUSY)
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text="Something went wrong.\nUpdate list of the tasks via /tasks")
        elif user.state == database.ALMOSTDONE:
            task_id = call.data.split("_")[-1]
            sol = call.data.split("_")[1]
            task = db.get_task(ObjectId(task_id))
            if task:
                if sol == "y":
                    task.set_done()
                    user.update_state(database.NOTBUSY)

                    bot.send_message(config.channelname,
                                     "Task \"{}\" done by {}".format(task.name, user))
                    bot.edit_message_text(chat_id=user.chat_id,
                                          message_id=call.message.message_id,
                                          text=str(task) + "\n\n*Done*",
                                          parse_mode="Markdown")
                elif sol == "n":
                    user.update_state(database.BUSY)
                    bot.edit_message_text(chat_id=user.chat_id,
                                          message_id=call.message.message_id,
                                          text=str(task) + "\n\n*Your task*",
                                          parse_mode="Markdown")


if __name__ == '__main__':
    bot.send_message(config.channelname,
                     "*Bot enabled*",
                     parse_mode="Markdown")
    logger.info("Bot started", extra={"chat": "Not chat"})
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error("Exception", exc_info=True)
    bot.send_message(config.channelname,
                    "*Bot disabled*",
                    parse_mode="Markdown")
