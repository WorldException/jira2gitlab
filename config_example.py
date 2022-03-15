
JIRA_URL = 'https://xxx.atlassian.net/'
JIRA_TOKEN = 'xxx'
JIRA_ACCOUNT = ('xxx@xxx.xxx', JIRA_TOKEN)
JIRA_PROJECT = 'PROJ1'

GITLAB_URL = 'https://xxx/'
GITLAB_TOKEN = 'xxx'
GITLAB_PROJECT = 12345
GITLAB_ACCOUNT = ('xxx@xxx.xx', 'application token')

ISSUE_TYPES_MAP = {
    'Subtask': 'issue',
    'Task': 'issue',
    'History': 'issue',
    'Epic': 'issue',
    'Bug': 'incident'
}

STATUS_NAMES_MAP = {
    'К выполнению': 'Open',
    'В работе': 'Open',
    'Test':'Open',
    'Готово':'Closed',
}

GITLAB_USER_NAMES = {
    'Name Family': 'user.name',
}

# ID of the group that contains your users.  In our case we have an everyone group
GITLAB_GROUP_USERS = 59