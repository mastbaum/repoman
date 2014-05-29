#!/usr/bin/env python

import time
import httplib
import urllib
import socket
import json
import uuid
import config

from repoman import tools
from repoman.handlers.handler import Handler

GLOBAL_SOCKET_TIMEOUT = 15
socket.setdefaulttimeout(GLOBAL_SOCKET_TIMEOUT)

class PullRequestWatcher:
    '''check the pull requests on a repository on a timer, and call repoman
    handlers on new arrivals.
    '''
    def __init__(self, user, repo, db_url, handlers, oauth_token=None):
        self.user = user
        self.repo = repo
        self.db_url = db_url
        self.handlers = handlers
        self.params = {'access_token': oauth_token} if oauth_token else {}

    def run(self, interval=5):
        '''poll the pulls at some interval'''
        while True:
            for user, repo, sha, doc in self.check_pulls():
                for handler in self.handlers:
                    handler.handle(doc)
            time.sleep(interval)

    def check_pulls(self):
        '''generate pull request summary documents'''
        url = '/repos/%s/%s/pulls' % (self.user, self.repo)
        conn = httplib.HTTPSConnection('api.github.com', timeout=20)
        req = conn.request('GET', url + '?' + urllib.urlencode(self.params))
        resp = conn.getresponse()
        payload = json.loads(resp.read())

        for pr in payload:
            try:
                # format appropriately for MergedPytuniaSubmitter
                issue_id = pr['html_url'].split('/')[-1]
                doc = {
                    'pull_url': pr['html_url'],
                    'base_repo_url': pr['base']['repo']['ssh_url'],
                    'base_repo_ref': pr['base']['ref'],
                    'url': pr['head']['repo']['ssh_url'],
                    'sha': pr['head']['sha'],
                    'full_name': pr['head']['repo']['full_name'],
                    'label': pr['head']['label'],
                    'message': '%s (%s): %s' % (issue_id, pr['head']['sha'][:10], pr['title']),
                    'author': pr['head']['user']['login']
                }

                user, repo = doc['full_name'].split('/')
                sha = doc['sha']

                conn, path, headers = tools.make_connection(self.db_url)
                conn.request('GET', '/pytunia-ondemand/' + sha, headers=headers)
                status = conn.getresponse().status

                # only proceed on 404, i.e. no test of this sha exists
                if status == 401 or status == 403:
                    raise Exception('Authentication to builder failed')
                elif status < 400:
                    continue
                elif status != 404:
                    raise Exception('Unable to reach builder, error ' + status + ' occurred')

                yield user, repo, sha, doc
            except TypeError:
                pass
            except socket.error:  # probably a timeout
                pass

    @staticmethod
    def set_commit_status(user, repo, sha, status, description, target_url, oauth_token):
        url = '/repos/%s/%s/statuses/%s' % (user, repo, sha)
        conn = httplib.HTTPSConnection('api.github.com')
        params = {'access_token': oauth_token}
        data = {
            'state': status,
            'target_url': target_url,
            'description': description
        }
        req = conn.request('POST', url + '?' + urllib.urlencode(params), json.dumps(data))
        resp = conn.getresponse()
        return resp.status, resp.read()


class MergedPytuniaSubmitter(Handler):
    '''push commits to the build tester'''
    def __init__(self, db_url, results_base_url, test_path, oauth_token=None):
        self.db_url = db_url
        self.results_base_url = results_base_url
        self.test_path = test_path
        self.oauth_token = oauth_token

    def handle(self, doc):
        docs = []
        sha = doc['sha']

        # record (revision) document
        record = {
            '_id': sha,
            'type': 'record',
            'description': doc['message'],
            'created': time.time(),
            'author': doc['author'],
            'changeset_url': doc['pull_url']
        }

        docs.append(record)

        # cppcheck task document
        cppcheck = {
            '_id': uuid.uuid4().get_hex(),
            'type': 'task',
            'name': 'cppcheck',
            'created': time.time(),
            'platform': 'linux',
            'kwargs': {
                'base_repo_url': doc['base_repo_url'],
                'base_repo_ref': doc['base_repo_ref'],
                'git_url' : doc['url'],
                'sha': sha,
            },
            'record_id': sha
        }

        docs.append(cppcheck)

        # fixme detector task document
        fixme = {
            '_id': uuid.uuid4().get_hex(),
            'type': 'task',
            'name': 'fixme',
            'created': time.time(),
            'platform': 'linux',
            'kwargs': {
                'base_repo_url': doc['base_repo_url'],
                'base_repo_ref': doc['base_repo_ref'],
                'git_url' : doc['url'],
                'sha': sha,
            },
            'record_id': sha
        }

        docs.append(fixme)

        # get task names with github api
        params = {'access_token': self.oauth_token} if self.oauth_token else {}
        params['recursive'] = 1

        tree_base_url = '/repos/%s/git/trees/' % doc['full_name']

        conn = httplib.HTTPSConnection('api.github.com')
        req = conn.request('GET', tree_base_url + sha + '?' + urllib.urlencode(params))
        resp = conn.getresponse()
        tree = json.loads(resp.read())['tree']

        tasknames = []
        for item in tree:
            p = self.test_path
            if item['type'] == 'tree' and item['path'][:len(p)] == p and item['path'] != p:
                tasknames.append(item['path'].split('/')[-1])

        # rattest task documents
        for taskname in tasknames:
            taskid = uuid.uuid4().get_hex()
            task = {
                '_id': taskid,
                'type': 'task',
                'name': 'rattest',
                'created': time.time(),
                'platform': 'linux',
                'kwargs': {
                    'base_repo_url': doc['base_repo_url'],
                    'base_repo_ref': doc['base_repo_ref'],
                    'git_url' : doc['url'],
                    'sha': sha,
                    'testname': taskname
                },
                'record_id': sha
            }

            docs.append(task)

        # post documents to database
        docs_json = json.dumps({'docs': docs})
        conn, path, headers = tools.make_connection(self.db_url)
        conn.request('POST', '/%s/_bulk_docs' % path, docs_json, headers)
        response = conn.getresponse()

        user, repo = doc['full_name'].split('/')
        status = 'pending'
        url = self.results_base_url + sha
        description = 'Build %s started' % sha[:7]
        code, body = PullRequestWatcher.set_commit_status(user, repo, sha, status, description, url, self.oauth_token)
        if code != 201:
            print 'MergedPytuniaSubmitter: error %i setting commit status on %s:' % (code, sha)
            print body

        print 'MergedPytuniaSubmitter: pushed %i documents to %s for record %s, response: %s %s' % (
            len(docs),
            self.db_url,
            sha,
            response.status,
            response.reason
        )


if __name__ == '__main__':
    print 'pullwatcher watching %s/%s' % (config.user, config.repo)

    submitter = MergedPytuniaSubmitter(config.db_url, config.results_base_url, config.test_path, config.oauth_token)

    watcher = PullRequestWatcher(config.user, config.repo, config.db_url, [submitter], config.oauth_token)

    watcher.run()

