import re
import os, sys
from xml.dom import NotFoundErr
import gitlab, gitlab.const
from gitlab.exceptions import GitlabCreateError
from . import model
import json
from typing import Optional, Dict
import requests
import uuid
from io import BytesIO
from hashlib import md5
import transliterate

backup_path = 'jira_backup'

# https://docs.gitlab.com/ee/api/notes.html

class IssueType:
    epic = 'Эпик'
    history = 'История'


def multiple_replace(text, adict):
    '''
     Gitlab markdown : https://docs.gitlab.com/ee/user/markdown.html
     Jira text formatting notation : https://jira.atlassian.com/secure/WikiRendererHelpAction.jspa?section=all
    '''
    if text is None:
        return ''
    t = text
    t = re.sub(r'(\r\n){1}', r'  \1', t)  # line breaks
    t = re.sub(r'\{code:([a-z]+)\}\s*', r'\n```\1\n', t)  # Block code
    t = re.sub(r'\{code\}\s*', r'\n```\n', t)  # Block code
    t = re.sub(r'\n\s*bq\. (.*)\n', r'\n\> \1\n', t)  # Block quote
    t = re.sub(r'\{quote\}', r'\n\>\>\>\n', t)  # Block quote #2
    t = re.sub(r'\{color:[\#\w]+\}(.*)\{color\}', r'> **\1**', t)  # Colors
    t = re.sub(r'\n-{4,}\n', r'---', t)  # Ruler
    t = re.sub(r'\[~([a-z]+)\]', r'@\1', t)  # Links to users
    t = re.sub(r'\[([^|\]]*)\]', r'\1', t)  # Links without alt
    t = re.sub(r'\[(?:(.+)\|)([a-z]+://.+)\]',
               r'[\1](\2)', t)  # Links with alt
    #t = re.sub(r'(\b%s-\d+\b)' % JIRA_PROJECT,
    #           r'[\1](%sbrowse/\1)' % JIRA_URL, t)  # Links to other issues
    
    # Lists
    t = re.sub(r'\n *\# ', r'\n 1. ', t)  # Ordered list
    t = re.sub(r'\n *[\*\-\#]\# ', r'\n   1. ', t)  # Ordered sub-list
    t = re.sub(r'\n *[\*\-\#]{2}\# ', r'\n     1. ', t)  # Ordered sub-sub-list
    t = re.sub(r'\n *\* ', r'\n - ', t)  # Unordered list
    t = re.sub(r'\n *[\*\-\#][\*\-] ', r'\n   - ', t)  # Unordered sub-list
    # Unordered sub-sub-list
    t = re.sub(r'\n *[\*\-\#]{2}[\*\-] ', r'\n     - ', t)
    # Text effects
    t = re.sub(r'(^|[\W])\*(\S.*\S)\*([\W]|$)', r'\1**\2**\3', t)  # Bold
    t = re.sub(r'(^|[\W])_(\S.*\S)_([\W]|$)', r'\1*\2*\3', t)  # Emphasis
    # Deleted / Strikethrough
    t = re.sub(r'(^|[\W])-(\S.*\S)-([\W]|$)', r'\1~~\2~~\3', t)
    t = re.sub(r'(^|[\W])\+(\S.*\S)\+([\W]|$)', r'\1__\2__\3', t)  # Underline
    t = re.sub(r'(^|[\W])\{\{(.*)\}\}([\W]|$)', r'\1`\2`\3', t)  # Inline code
    # Titles
    t = re.sub(r'\n?\bh1\. ', r'\n# ', t)
    t = re.sub(r'\n?\bh2\. ', r'\n## ', t)
    t = re.sub(r'\n?\bh3\. ', r'\n### ', t)
    t = re.sub(r'\n?\bh4\. ', r'\n#### ', t)
    t = re.sub(r'\n?\bh5\. ', r'\n##### ', t)
    t = re.sub(r'\n?\bh6\. ', r'\n###### ', t)
    # Emojis : https://emoji.codes
    t = re.sub(r':\)', r':smiley:', t)
    t = re.sub(r':\(', r':disappointed:', t)
    t = re.sub(r':P', r':yum:', t)
    t = re.sub(r':D', r':grin:', t)
    t = re.sub(r';\)', r':wink:', t)
    t = re.sub(r'\(y\)', r':thumbsup:', t)
    t = re.sub(r'\(n\)', r':thumbsdown:', t)
    t = re.sub(r'\(i\)', r':information_source:', t)
    t = re.sub(r'\(/\)', r':white_check_mark:', t)
    t = re.sub(r'\(x\)', r':x:', t)
    t = re.sub(r'\(!\)', r':warning:', t)
    t = re.sub(r'\(\+\)', r':heavy_plus_sign:', t)
    t = re.sub(r'\(-\)', r':heavy_minus_sign:', t)
    t = re.sub(r'\(\?\)', r':grey_question:', t)
    t = re.sub(r'\(on\)', r':bulb:', t)
    # t = re.sub(r'\(off\)', r'::', t) # Not found
    t = re.sub(r'\(\*[rgby]?\)', r':star:', t)
    for k, v in adict.items():
        t = re.sub(k, v, t)
    return t


class GitLabProjectImporter(object):
    
    def __init__(self, url: str, token: str, project_path: str, jira_name:str, jira_project_key: str):
        self.url = url
        self.token = token
        self.project_path = project_path
        self.jira_name = jira_name
        self.jira_project_key = jira_project_key
        self.gitlab = gitlab.Gitlab(url, token)
        self.gitlab.auth()

        database_filename = os.path.join(backup_path, jira_name, 'data.sqlite')
        print(f'open database: {database_filename}')
        self.db = model.connect(database_filename)
        self.project: gitlab.RESTObject = self.get_project_by_path(project_path)
        #self.project = self.gitlab.projects.get(project_id) #get project info
        print(f"project name: {self.project.name}; {self.project.web_url}")
        #print(self.project)

    def get_project_by_path(self, path):
        for project in self.gitlab.projects.list(all=True):
            if project.path_with_namespace == path:
                return project
        raise NotFoundErr(f"Not found project:{path}")

    def create_default_labels(self):
        try:
            self.project.labels.create({'name': 'TO DO', 'color': '#6699cc'})
            self.project.labels.create({'name': 'IN PROGRESS', 'color': '#009966'})
            self.project.labels.create({'name': 'TESTING', 'color': '#ed9121'})
        except GitlabCreateError:
            pass

    def issue_title(self, key, name):
        return f"[{key.strip()}] {name.strip()}"

    def create_issue(self, issue: model.Issuie):
        
        if self.find_issue_in_project(issue.name, issue.key, True):
            return
        
        jira_issue = json.loads(str(issue.data))
        issue_info = json.loads(str(issue.info))

        title = self.issue_title(issue.key, issue.name)

        labels = [jira_issue['fields']['issuetype']['name']]
        labels.append(jira_issue['fields']['status']['name'])
        labels.append(jira_issue['key'])
        labels.extend(jira_issue['fields']['labels'])
        
        replacements = self.attach_files(issue.key, issue_info)
        description = multiple_replace(jira_issue['fields']['description'], replacements)

        data = {
            'assignee_ids': [
                self.accountId_to_userid(jira_issue['fields']['assignee']),
                self.accountId_to_userid(jira_issue['fields']['creator'])
            ],
            'author_id': self.accountId_to_userid(jira_issue['fields']['creator']),
            'title': title,
            'description': description,
            'labels': ", ".join(labels),
            'created_at': jira_issue['fields']['created'],
            'due_date': jira_issue['fields']['duedate'],
            'updated_at': jira_issue['fields']['updated']
        }

        ms = None
        parent_task = jira_issue['fields'].get('parent', None)
        if parent_task:
            # совпадает не только по имени но и по тегу/ ключу задачи
            if parent_task['fields']['issuetype']['name'] == IssueType.epic:
                ms = self.find_milestone_in_project(parent_task['fields']['summary'], parent_task['key'], True)
                data['milestone_id'] = ms['id']

        gl_issue = self.project.issues.create(data)

        # Recreate each Jira comment in Gitlab
        for comment in issue_info['fields']['comment']['comments']:
            author = comment['author']['displayName']
            commentbody = ""
            # Add sudo header if appropriate
            commentbody = 'Original comment by {}\n\n'.format(author)
            commentbody = commentbody + multiple_replace(comment['body'], replacements)
            body = {
                'body': commentbody,
                'author_id': self.accountId_to_userid(comment['author'])
            }
            comment_note = gl_issue.notes.create(body)

        # If the Jira issue was closed, mark the Gitlab one closed as well
        if jira_issue['fields']['status']['statusCategory']['key'] == "done":
            gl_issue.state_event = 'close'
        #gl_issue.issue_type = ISSUE_TYPES_MAP[issue['fields']['issuetype']['name']].lower()
        
        gl_issue.save()

    def create_milestone(self, issue):
        
        if self.find_milestone_in_project(issue.name, issue.key, True):
            return
        
        jira_issue = json.loads(str(issue.data))
        issue_info = json.loads(str(issue.info))

        title = self.issue_title(issue.key, issue.name)

        labels = [jira_issue['fields']['issuetype']['name']]
        labels.append(jira_issue['fields']['status']['name'])
        labels.extend(jira_issue['fields']['labels'])
        
        replacements = self.attach_files(issue.key, issue_info)

        description = f"**{jira_issue['key']}**\n\n"+\
            multiple_replace(jira_issue['fields']['description'], replacements)

        data = {
            #'assignee_ids': [],
            'author_id': self.accountId_to_userid(jira_issue['fields']['creator']),
            'title': title,
            'description': description,
            'labels': ", ".join(labels),
            'created_at': jira_issue['fields']['created'],
            'due_date': jira_issue['fields']['duedate'],
            'updated_at': jira_issue['fields']['updated']
        }

        gl_issue = self.project.milestones.create(data)

        # If the Jira issue was closed, mark the Gitlab one closed as well
        if jira_issue['fields']['status']['statusCategory']['key'] == "done":
            gl_issue.state_event = 'close'
        gl_issue.save()
    
    def find_issue_in_project(self, name, key, only_check=False):
        gl_issues = self.project.search(gitlab.const.SEARCH_SCOPE_ISSUES, name)
        if not gl_issues:
            gl_issues = self.project.search(gitlab.const.SEARCH_SCOPE_ISSUES, self.issue_title(key, name))
        if gl_issues:
            for gl_issue in gl_issues:
                if key in gl_issue['labels']:
                    if only_check:
                        return True
                    return self.project.issues.get(gl_issue['iid'])
        return None

    def find_milestone_in_project(self, name, key, return_dict=False):
        for item in self.project.search(gitlab.const.SEARCH_SCOPE_MILESTONES, self.issue_title(key, name)):
            if return_dict:
                return item
            return self.project.milestones.get(item['id'])
        return None

    def create_links(self):
        for issue in model.Issuie.select().where(model.Issuie.project_key == self.jira_project_key):
            jira_issue = json.loads(str(issue.data))
            parent_task = jira_issue['fields'].get('parent', None)
            if parent_task:
                gl_issue = self.find_issue_in_project(issue.name, issue.key)
                if gl_issue:
                    # совпадает не только по имени но и по тегу/ ключу задачи
                    if parent_task['fields']['issuetype']['name'] == IssueType.epic:
                        #gl_issue.milestone = self.find_milestone_in_project(parent_task['fields']['summary'], True)
                        #gl_issue.save()
                        
                        #ms = self.find_milestone_in_project(parent_task['fields']['summary'])
                        #gl_issue.milestone = {'project_id': self.project.id, 'iid': ms.iid}
                        pass
                        
                        #self.find_milestone_in_project(parent_task['fields']['summary'])
                    else:
                        parent_issue = self.find_issue_in_project(parent_task['fields']['summary'], parent_task['key'])
                        if parent_issue:
                            #if len(list(filter(lambda x: x.issue_iid == parent_issue.iid and x.project_id == self.project.id, gl_issue.links.list()))) == 0:
                            try:
                                gl_issue.links.create({
                                    'target_project_id': self.project.id,
                                    'target_issue_iid': parent_issue.iid
                                })
                            except GitlabCreateError as er:
                                pass

    def attach_files(self, key, issue_info):
        replacements = {}
        dst_path = os.path.join(
            backup_path,
            self.jira_name,
            self.jira_project_key,
            key
        )
        for attachment in issue_info['fields']['attachment']:
            
            filename = os.path.join(dst_path, attachment['filename'])
            if not os.path.exists(filename):
                raise FileNotFoundError(filename)

            with open(filename, 'rb') as f:
                _content = BytesIO(f.read())

            #str(uuid.uuid4()),
            #f"{key}_{attachment['id']}_{attachment['filename']}"
            # исключить дублирование файлов на сервере
            filename_url = md5(f"{key}_{attachment['id']}_{attachment['filename']}".encode()).hexdigest()

            file_info_response = requests.post(
                self.url + f'api/v4/projects/{self.project.id}/uploads',
                headers={
                    'PRIVATE-TOKEN': self.token
                },
                files={
                    'file': (
                        filename_url,
                        _content
                    )
                },
                verify=True
            )
            del _content

            try:
                file_info = file_info_response.json()
                # now we got the upload URL. Let's post the comment with an
                # attachment
                if 'url' in file_info:
                    key = f"!{attachment['filename']}[^!]*!"
                    value = f"![{attachment['filename']}]({file_info['url']})"
                    replacements[key] = value
            except json.JSONDecodeError as err:
                if 'Request Entity Too Large' in str(err):
                    print(f"! large: {filename} size:{os.path.getsize(filename)}")
                    continue
            
        return replacements

    def clean(self, delete=False):
        current_user = self.gitlab.user.name
        # require sudo token permission
        print('remove issues')
        for issue in self.project.issues.list(all=True):
            if current_user == issue.author['name']:
                print(f"delete issue title:{issue.title}; author:{issue.author['name']}")
                if delete:
                    issue.delete()

        print('remove milestones')
        for issue in self.project.milestones.list(all=True):
            if self.jira_project_key in issue.description:
                print(f"delete milestone title:{issue.title}")
                if delete:
                    issue.delete()
        
    def import_issues(self):
        for issue in model.Issuie.select().where(model.Issuie.project_key == self.jira_project_key):
            print(f"create issue: {self.issue_title(issue.key, issue.name)}")
            self.create_issue(issue)

    def import_epics(self):
        for epic in model.Issuie.select().where((model.Issuie.ctype == 'Эпик') & (model.Issuie.project_key == self.jira_project_key)):
            print(f"create milestone: {self.issue_title(epic.key, epic.name)}")
            self.create_milestone(epic)
        
    def auto_set_users(self):
        for user in self.gitlab.users.list(all=True):
            username_en = transliterate.translit(user.name, 'ru', reversed=True)
            print(user.name)
            accountJira = list(model.Account.select().where(
                (model.Account.displayName == user.name) | 
                (model.Account.displayName == username_en) | 
                (model.Account.searchName == user.name) | 
                (model.Account.emailAddress == user.email)
            ))
            print(f"{user.id}: {user.username}; {user.name}; {user.email}")
            if accountJira:
                #print(accountJira[0])
                account = accountJira[0]
                account.gitlabName = user.name
                account.gitlabLogin = user.username
                account.gitlabEmail = user.email
                account.gitlabId = user.id
                account.gitlabData = json.dumps({
                    "id": user.id,
                })
                account.save()
        self.db.commit()

    def accountId_to_userid(self, jiraAccount: Dict) -> Optional[int]:
        # пользователь гит лаба по ид жиры
        if not jiraAccount:
            return None
        account: Optional[model.Account] = model.Account.get_or_none(model.Account.accountId == jiraAccount['accountId'])
        if account:
            return account.gitlabId
        return None
