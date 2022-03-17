from jira2gitlab import jira

# Example export project to local files (issues database and attachments)

# name from url https://{name}.atlassian.net/
# token from https://id.atlassian.com/manage-profile/security/api-tokens
jira.configure('name', 'you_mail@gmail.com', 'jira_token')

# export all projects
jira.export_projects()
# export some project
jira.export_projects(['AC', 'AB'])

# for download export-users.csv 
# 1. go https://{site}.atlassian.net/jira/people/search and click "Manage users"
# 2. click "Export users"
jira.save_users(jira.export_users('export-users.csv'))
# grab users from tasks
jira.save_users(jira.grab_users())
