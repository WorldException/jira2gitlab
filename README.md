# jira2gitlab

Migrate Issue with comments and attachements from Jira to Gitlab.

## Installation

```
python >= 3.8
python-gitlab
requests 
=======
Migrate from Jira to Gitlab.

## Features

- Export Jira to local database and attachements files.
- Export all projects
- Multi sites
- Sync users by name, email, manualy (edit account.searchName into database)
- Convert: Issues, Members, Comments, Attachements, Epic as Milestones, Markdown

## Installation

Requirements

```
python >= 3.8
pipenv
```

## Using

Fill settings `config_example.py` file and run `python jira2gitlab.py`
=======
1. Export Jira project. Copy and edit `export_example.py`. Run your `python export_some.py`.
After done you will have `jira_backup` folder into project dir.
2. Sync users. Copy and edit `sync_users_example.py`, then run them.
Database table Account will be filled with gitlab accounts info.
3. Import into gitlab. Copy `import_example.py`, edit and run you file.

## About

Thanks to https://github.com/owentl/gitlab-tools

