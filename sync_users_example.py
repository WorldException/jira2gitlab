from jira2gilab.importer import GitLabProjectImporter

# https://{jira_name}.atlassian.net/jira/software/projects/{jira_code}
# https://gitlab.some.on/project_name/SOME/repo
gl = GitLabProjectImporter('https://gitlab.some.on/', 'token', 'project_name/SOME/repo', 'jira_name', 'jira_code')

# sync users between jira database and gitlab by name or email or searchName (set manualy)
gl.auto_set_users()
