from email.policy import default
from typing import Text
from peewee import Model, SqliteDatabase, TextField, IntegerField, CharField, IntegrityError
from contextlib import contextmanager

class Project(Model):
    key=CharField()
    name=CharField()
    projectType=CharField()


class Issuie(Model):
    key = CharField()
    name = TextField()
    project_key = CharField()
    ctype=CharField()
    status=CharField()
    data = TextField()
    info = TextField()

class Account(Model):
    displayName = CharField()
    emailAddress = CharField()
    accountId = CharField(unique=True)
    jiraData = TextField()

    searchName = CharField(default='')

    gitlabName = CharField(default='')
    gitlabLogin = CharField(default='')
    gitlabEmail = CharField(default='')
    gitlabId = IntegerField(null=True)
    gitlabData = TextField(default='')

def connect(filename):
    db = SqliteDatabase(filename)
    db.connect()
    db.bind([Project, Issuie, Account])
    return db


@contextmanager
def create_db(filename):
    db = connect(filename)
    db.create_tables([Project, Issuie, Account])
    try:
        yield db
    finally:
        db.commit()
        db.close()
    

