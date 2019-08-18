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


def send_task(chat_id):
    pass


@bot.message_handler(commands=['start'])
def start(message):
    """
    Create new user in system
    :param message:
    :return:

    states:
        0 - not busy
        1 - choosing task
        2 - busy
    """
    create_or_find(message.chat.id)
    bot.send_message(message.chat.id, "Hello! Welcome to AMC Tasks")


@bot.message_handler(commands=['tasks'])
def list_of_tasks(message):
    user = create_or_find(message.chat.id)
    if user["state"] == 0:
        pass
    elif user["state"] == 1:
        pass
    elif user["state"] == 2:
        task = db.tasks.find_one({"chat_id": message.chat.id})
        if task is None:
            db.users.update_one({"chat_id": message.chat.id}, {"$set": {"state": 1}})
            raise NotImplementedError




if __name__ == '__main__':
    bot.polling(none_stop=True)
