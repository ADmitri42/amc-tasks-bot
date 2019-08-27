from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId

NOTBUSY = 0
BUSY = 1
ALMOSTDONE = 2

SLOTDURATION = 60*8

class User:
    def __init__(self, chat_id, username, first_name, last_name, state, db):
        self.chat_id = chat_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.state = state
        self.db = db

    @staticmethod
    def from_dict(user, db):
        return User(user['chat_id'],
                    user['username'],
                    user['first_name'],
                    user['last_name'],
                    user['state'],
                    db)

    def __str__(self):
        name = ''
        if self.first_name:
            name += self.first_name
        if self.last_name:
            name += ' ' + self.last_name
        if self.username:
            name += '(@' + self.username + ')'

        return name

    def update_state(self, new_state):
        self.db.users.update_one(
            {
                "chat_id": self.chat_id
            },
            {
                "$set":
                    {
                        "state": new_state
                    }
            }
        )
        self.state = new_state


class Task:
    def __init__(self, name, deadline, done, _id, db, executor=None):
        self.name = name
        self.deadline = deadline
        self.id = _id
        self.db = db
        self.executor = executor
        self.done=done

    @staticmethod
    def from_dict(task, db):
        return Task(**task, db=db)

    def __str__(self):
        return "*{}*\n{}".format(self.name, self.deadline)

    def add_executor(self, executor: User):
        self.db.tasks.update_one({"_id": self.id}, {"$set": {"executor": executor.chat_id}})
        self.executor = executor.chat_id

    def set_done(self):
        self.db.tasks.update_one({"_id": self.id}, {"$set": {"done": True}})
        self.done = True


class Database:
    def __init__(self, mongo_uri):
        self.client = MongoClient(mongo_uri)
        self.db = self.client.AMCtasks

    def create_user(self, chat_id, username, first_name, last_name):
        user = {
            "chat_id": chat_id,
            "state": 0,
            "username": username,
            "first_name": first_name,
            "last_name": last_name
        }
        self.db.users.insert_one(user)
        return self.get_user(chat_id)

    def get_user(self, chat_id):
        """
        Return User or None if user doesn't exists
        :param chat_id:
        :return:
        """
        user = self.db.users.find_one({"chat_id": chat_id})
        if user:
            user = User.from_dict(user, self.db)

        return user

    def get_task(self, task_id: ObjectId):
        task = self.db.tasks.find_one({"_id": task_id})
        if task is None:
            raise ValueError("Id {} not exists".format(task_id))
        task = Task.from_dict(task, self.db)

        return task

    def find_task(self, executor: User):
        task = self.db.tasks.find_one(
            {"$and": [{"executor": executor.chat_id}, {"done": False}]}, {'_id': 1})
        if task:
            return self.get_task(task['_id'])
        else:
            return None

    def get_active_tasks_id(self):
        tasks_id = self.db.tasks.find({
                        "$and": [{"deadline": {
                            "$gte": datetime.now(),
                            "$lt": datetime.now() + timedelta(0, 3600 * 8)
                        }}, {"executor": {"$exists": False}}]
                    }, {'_id'}).sort([('deadline', 1)])

        return list(tasks_id)
