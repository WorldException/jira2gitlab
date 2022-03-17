from importlib.resources import open_binary
from typing import Dict, Optional, List
import requests
from requests.auth import HTTPBasicAuth
from io import StringIO
from io import BytesIO
import json
import sys, os
from . import model
from .retries import on_except_retry
import csv


backup_path = 'jira_backup'

os.makedirs(backup_path, exist_ok=True)

JIRA_URL = 'https://xxx.atlassian.net/'
JIRA_TOKEN = ''
JIRA_ACCOUNT = ('', JIRA_TOKEN)
JIRA_NAME = ''
db_filename = ''


def configure(name, login, token):
    global JIRA_NAME, JIRA_ACCOUNT, JIRA_TOKEN, JIRA_URL, JIRA_URL, db_filename

    JIRA_NAME = name
    JIRA_TOKEN = token
    JIRA_URL = f'https://{name}.atlassian.net/'
    JIRA_ACCOUNT = (login, token)
    db_filename = os.path.join(backup_path, JIRA_NAME, 'data.sqlite' )
    os.makedirs(os.path.dirname(db_filename), exist_ok=True)

# Jira Query
#JQL = 'key=PRO-1182'
# all tasks
#JQL = f'project={JIRA_PROJECT}+ORDER+BY+createdDate+ASC&maxResults=10000'
# only unresolved
#JQL = f'project={JIRA_PROJECT}+AND+(resolution=Unresolved+OR+Sprint+in+openSprints())+ORDER+BY+createdDate+ASC&maxResults=10000'

# set this to false if JIRA / Gitlab is using self-signed certificate.
VERIFY_SSL_CERTIFICATE = True

# the Jira Epic custom field
JIRA_EPIC_FIELD = 'customfield_10006'

# the Jira Sprints custom field
JIRA_SPRINT_FIELD = 'customfield_10005'

# the Jira story points custom field
JIRA_STORY_POINTS_FIELD = 'customfield_10002'


def path_proj(path, filename):
    dst_path = os.path.join(backup_path, path)
    os.makedirs(dst_path, exist_ok=True)
    return os.path.join(dst_path, filename)


@on_except_retry(30, 2)
def jira_getfile(url):
    return requests.get(
        url,
        auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
    )


def export_attachements(attachments, dst_path: str):
    replacements = {}
    if len(attachments):
        for attachment in attachments:
            
            if os.path.exists(dst_path):
                continue

            _file = jira_getfile(attachment['content'])
            
            with open(path_proj(dst_path, attachment['filename']), 'wb') as f:
                f.write(_file.content)

    return replacements


@on_except_retry(30, 2)
def jira_get(url, params=None):
    # Jira API documentation : https://developer.atlassian.com/static/rest/jira/6.1.html
    jira_issues_request = requests.get(
        JIRA_URL + url,
        auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
        headers={'Content-Type': 'application/json'},
        params=params
    )
    return jira_issues_request


def jira_admin(url, params=None):
    return requests.get(
        'https://api.atlassian.com/' + url,
        #auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {JIRA_TOKEN}'
        },
        params=params
    )


def jira_projects():
    return jira_get('/rest/api/2/project').json()


def export_projects(project_filter: Optional[List[str]]=None):

    with model.create_db(db_filename) as db:
        projects = jira_projects()

        for project in projects:

            if project_filter:
                if not project['key'] in project_filter:
                    continue
            
            print(f"Export project: {project['key']}")
            
            if not model.Project.get_or_none(model.Project.id == project['id']):
                model.Project.create(
                    id=project['id'],
                    key=project['key'],
                    name=project['name'],
                    projectType=project['projectTypeKey']
                )

            JQL = f"project={project['key']}+ORDER+BY+createdDate+ASC&maxResults=500"
            jira_issues = jira_get('rest/api/2/search?jql=' + JQL).json().get('issues', [])
            
            if not jira_issues:
                print('Not found issues, check access rights')

            startAt = 0
            while jira_issues:
                print(f'StartAt: {startAt}')
                for issue in jira_issues:
                    
                    if model.Issuie.get_or_none(model.Issuie.id == issue['id']):
                        continue

                    print("issue: {}; {} = {} ({})".format(
                        issue['key'],
                        issue['fields']['summary'],
                        issue['fields']['status']['statusCategory']['key'],
                        issue['fields']['issuetype']['name']
                    ))

                    # get comments and attachments from Jira
                    issue_info = jira_get(f"rest/api/2/issue/{issue['id']}/?fields=attachment,comment").json()
                    
                    model.Issuie.create(
                        id=issue['id'],
                        key=issue['key'],
                        name=issue['fields']['summary'],
                        project_key=issue['fields']['project']['key'],
                        ctype=issue['fields']['issuetype']['name'],
                        status=issue['fields']['status']['name'],
                        data=json.dumps(issue),
                        info=json.dumps(issue_info)
                    )

                    replacements = export_attachements(
                        issue_info['fields']['attachment'], 
                        os.path.join(
                            JIRA_NAME,
                            issue['fields']['project']['key'],
                            issue['key']
                        )
                    )
                
                startAt += len(jira_issues)
                JQL = f"project={project['key']}+ORDER+BY+createdDate+ASC&maxResults=500&startAt={startAt}"
                jira_issues = jira_get('rest/api/2/search?jql=' + JQL).json().get('issues', [])

def grab_users():
    db = model.connect(db_filename)
    users = {}
    for issue in model.Issuie.select():
        data = json.loads(issue.data)

        creator = data['fields']['creator']
        if creator:
            users[creator['accountId']] = creator
        
        reporter = data['fields']['reporter']
        if reporter:
            users[reporter['accountId']] = reporter
        
        assignee = data['fields']['assignee']
        if assignee:
            users[assignee['accountId']] = assignee

        info = json.loads(issue.info)
        for comment in info['fields']['comment']['comments']:
            author = comment['author']
            if author:
                users[author['accountId']] = author
    return users

def save_users(users: Dict[str, Dict]):
    with model.create_db(db_filename) as db:
        for accountId, user in users.items():
            try:
                model.Account.create(
                    accountId=accountId,
                    displayName=user['displayName'],
                    emailAddress=user.get('email',''),
                    jiraData=json.dumps(user)
                )
            except model.IntegrityError as e:
                pass

def export_users(export_csv_filename):
    csv_users = {}
    with open(export_csv_filename, 'rt') as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_users[row['User id']] = row
    ret = {}
    users_jira = jira_get('rest/api/3/users').json()
    for user in users_jira:
        user['email'] = csv_users.get(user['accountId'], {}).get('email', '')
        ret[user['accountId']] = user
    return ret

def export_user(accountId):
    #return jira_get('rest/api/3/user', {'accountId': accountId}).json()
    return jira_get('rest/api/3/user/email', {'accountId': accountId})
