from pymongo import MongoClient

NOTBUSY = 0
BUSY = 1
ALMOSTDONE = 2


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
    def __init__(self, name, deadline, _id):
        self.name = name
        self.deadline = deadline
        self._id = _id

    @staticmethod
    def from_dict(task):
        pass

    def __str__(self):
        return "*{}*\n{}".format()

class Database:
    def __init__(self, mongo_uri):
        self.client = MongoClient(mongo_uri)
        self.db = self.client

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

