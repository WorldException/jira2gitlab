from jira2gilab.importer import GitLabProjectImporter

# Import jira project from db into gitlab repo

# https://{jira_name}.atlassian.net/jira/software/projects/{jira_code}
# https://gitlab.some.on/project_name/SOME/repo
gl = GitLabProjectImporter('https://gitlab.some.on/', 'token', 'project_name/SOME/repo', 'jira_name', 'jira_code')

# remove all create issues where author this user
gl.clean(True)

# load epics as milestones
gl.import_epics()

# load issues
gl.import_issues()

# make links between milestones and issues
gl.create_links()