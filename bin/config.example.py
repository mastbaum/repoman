from repoman.handlers import *

git_url = 'git@github.com:OWNER/REPO'

pytunia_submitter_settings = {
    'git_url': git_url,
    'test_path': 'test/full',
    'changeset_base_url': 'https://github.com/OWNER/REPO/commit/',
    'tree_base_url': '/repos/OWNER/REPO/git/trees/',
    'oauth_token': 'this is a secret'
}

handlers = {
    'REPO': [
        Repeater('http://localhost:8452', git_url),   # rebuild docs
        Repeater('http://localhost:8453', git_url),   # mirror
        Emailer(),                                    # email a list
        PytuniaSubmitter(*pytunia_submitter_settings) # submit to build tester
    ]
}

