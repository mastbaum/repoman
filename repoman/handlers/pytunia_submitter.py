from handler import Handler

from ..log import log

import time
import httplib
import json
import uuid
import urllib

class PytuniaSubmitter(Handler):
    '''push commits to the build tester'''
    def __init__(self, git_url, changeset_base_url, tree_base_url, test_path, oauth_token):
        self.git_url = git_url
        self.changeset_base_url = changeset_base_url
        self.tree_base_url = tree_base_url
        self.test_path = test_path
        self.oauth_token = oauth_token

    def handle(self, doc):
        params = {'access_token': self.oauth_token, 'recursive': 1}
        docs = []

        for commit in doc['commits']:
            sha = commit['id']

            # record (revision) document
            record = {'_id': sha,
                      'type': 'record',
                      'description': commit['message'],
                      'created': time.time(),
                      'author': commit['author']['name'],
                      'changeset_url': self.changeset_base_url + sha}
            docs.append(record)

            # cppcheck task document
            cppcheck = {'_id': uuid.uuid4().get_hex(),
                        'type': 'task',
                        'name': 'cppcheck',
                        'created': time.time(),
                        'platform': 'linux',
                        'kwargs': {'sha': sha,
                                   'git_url' : self.git_url},
                        'record_id': sha}
            docs.append(cppcheck)

            # fixme detector task document
            fixme = {'_id': uuid.uuid4().get_hex(),
                    'type': 'task',
                    'name': 'fixme',
                    'created': time.time(),
                    'platform': 'linux',
                    'kwargs': {'sha': sha,
                               'git_url': self.git_url},
                    'record_id': sha}
            docs.append(fixme)

            # get task names with github api
            tasknames = []
            conn = httplib.HTTPSConnection('api.github.com')
            req = conn.request('GET', self.tree_base_url + sha + '?' + urllib.urlencode(params))
            resp = conn.getresponse()
            tree = json.loads(resp.read())['tree']

            for item in tree:
                if item['type'] == 'tree' and item['path'][:len(self.test_path)] == self.test_path and item['path'] != self.test_path:
                    tasknames.append(item['path'].split('/')[-1])

            # rattest task documents
            for taskname in tasknames:
                taskid = uuid.uuid4().get_hex()
                task = {'_id': taskid,
                        'type': 'task',
                        'name': 'rattest',
                        'created': time.time(),
                        'platform': 'linux',
                        'kwargs': {'sha': sha,
                                   'git_url' : self.git_url,
                                   'testname': taskname},
                        'record_id': sha}
                docs.append(task)


        docs_json = json.dumps(docs)

        #push to db
        log.write('PytuniaSubmitter: pushed %i documents to pytunia for record %s' % (len(docs), sha))

