#!/usr/bin/env python

import time
import httplib
import urllib
import socket
import json
import uuid
import socket
import config

from repoman import tools
from repoman.handlers.handler import Handler

GLOBAL_SOCKET_TIMEOUT = 15
socket.setdefaulttimeout(GLOBAL_SOCKET_TIMEOUT)

class PullRequestWatcher:
    '''Check the pull requests on a repository on a timer, and call repoman
    handlers on new arrivals.

    :param user: GitHub user/organization name
    :param repo: Repository name
    :param db_url: URL of build testing DB
    :param handlers: A list of repoman Handlers to apply to PRs
    :param oauth_token: GitHub OAuth token
    '''
    def __init__(self, user, repo, db_url, handlers, oauth_token=None):
        self.user = user
        self.repo = repo
        self.db_url = db_url
        self.handlers = handlers
        self.params = {'access_token': oauth_token} if oauth_token else {}

    def run(self, interval=5):
        '''Poll the pulls at some interval, and apply handlers to incoming PRs.

        :param interval: Time interval between checks (seconds)
        '''
        while True:
            for user, repo, sha, doc in self.check_pulls():
                if doc is None:
                    continue
                for handler in self.handlers:
                    handler.handle(doc)
            self.check_finished()
            time.sleep(interval)

    def check_finished(self):
        '''Check if all the tests associated with a PR have completed, and
        update the status appropriately.
        '''
        url = '/repos/%s/%s/pulls' % (self.user, self.repo)
        conn = httplib.HTTPSConnection('api.github.com')
        headers = {'User-agent': config.user_agent}
        try:
            req = conn.request('GET', url + '?' + urllib.urlencode(self.params), headers=headers)
        except socket.error as e:
            print 'socket.error on request:', e
            return
        resp = conn.getresponse()
        try:
            data = resp.read()
        except socket.error as e:
            print 'socket.error on read:', e
            return

        if resp.status > 399:
            return

        try:
            payload = json.loads(data)
        except ValueError:
            print 'ValueError:', data
            return

        def check_and_update_status(sha):
            # check that we haven't already completed this sha
            headers = {'User-agent': config.user_agent}
            conn, path, headers = tools.make_connection(self.db_url, headers=headers)
            url = '%s/%s' % (self.db_url, sha)
            try:
                conn.request('GET', url, headers=headers)
            except socket.error as e:
                print 'socket.error:', e
                return
            response = conn.getresponse()
            payload = json.loads(response.read())

            if 'completed' in payload and payload['completed']:
                return

            # loop over tests to see if we're done, and what the status is
            overall_success = True
            all_finished = True
            reason = 'Unknown'

            conn, path, headers = tools.make_connection(self.db_url, headers=headers)
            query = 'startkey=["%s",1]&endkey=["%s",1,{}]' % (sha, sha)
            url = '%s/_design/pytunia/_view/tasks_by_record?%s' % (self.db_url, query)
            try:
                conn.request('GET', url, headers=headers)
            except socket.error as e:
                print 'socket.error:', e
                return
            response = conn.getresponse()
            payload = json.loads(response.read())['rows']

            for row in payload:
                doc = row['value']
                if 'error' in doc:
                    return

                if not 'completed' in doc:
                    all_finished = False
                    break

                if 'results' in doc and not doc['results']['success']:
                    overall_success = False
                    if reason == 'Unknown':
                        if 'reason' in doc['results']:
                            reason = doc['results']['reason']
                        else:
                            reason = 'Failed ' + doc['name']
                    else:
                        reason = 'Multiple tests failed'
                        break

            if all_finished:
                if overall_success:
                    status = 'success'
                    reason = 'All tests passed'
                else:
                    status = 'failure'

                print 'Updating status for commit %s: %s (%s)' % (sha, status, reason)

                url = config.results_base_url + sha
                code, body = PullRequestWatcher.set_commit_status(config.user, self.repo, sha, status, reason, url, self.params['access_token'])

                if code >= 400:
                    print 'Error %i updating status on commit %s: %s' % (code, sha, body)

                # update the document in the build test db to indicate completion
                conn, path, headers = tools.make_connection(self.db_url, headers=headers)
                url = '%s/%s' % (self.db_url, sha)
                try:
                    conn.request('GET', url, headers=headers)
                except socket.error as e:
                    print 'socket.error:', e
                    return
                response = conn.getresponse()
                payload = json.loads(response.read())

                payload['completed'] = True

                conn, path, headers = tools.make_connection(self.db_url, headers=headers)
                url = '%s/%s' % (self.db_url, sha)
                try:
                    conn.request('PUT', url, json.dumps(payload), headers=headers)
                except socket.error as e:
                    print 'socket.error:', e
                    return
                response = conn.getresponse()
                if code != 201:
                    print 'Error %i updating DB for commit %s: %s' % (code, sha, response.read())

        for pr in payload:
            try:
                sha = pr['head']['sha']
                check_and_update_status(sha)
            except TypeError:
                print 'Caught TypeError with pr =', pr

    def check_pulls(self):
        '''Generate pull request summary documents.

        :returns: Tuple of repo user, repo name, head sha, metadata document
        '''
        url = '/repos/%s/%s/pulls' % (self.user, self.repo)
        conn = httplib.HTTPSConnection('api.github.com')
        headers = {'User-agent': config.user_agent}
        try:
            req = conn.request('GET', url + '?' + urllib.urlencode(self.params), headers=headers)
        except socket.error as e:
            print 'Socket error:', e
            yield None, None, None, None
            return
        try:
            resp = conn.getresponse()
        except Exception as e:
            print 'Exception: ' + str(e)
            yield None, None, None, None
            return
        data = resp.read()
        try:
            payload = json.loads(data)
        except ValueError:
            print 'Malformed response:', data
            yield None, None, None, None
            return

        for pr in payload:
            try:
                # format appropriately for MergedPytuniaSubmitter
                doc = {
                    'pull_url': pr['html_url'],
                    'base_repo_url': pr['base']['repo']['ssh_url'],
                    'base_repo_ref': pr['base']['ref'],
                    'url': pr['head']['repo']['ssh_url'],
                    'sha': pr['head']['sha'],
                    'full_name': pr['head']['repo']['full_name'],
                    'label': pr['head']['label'],
                    'message': pr['title'],
                    'author': pr['head']['user']['login']
                }

                user, repo = doc['full_name'].split('/')
                sha = doc['sha']

                conn, path, headers = tools.make_connection(self.db_url, headers=headers)
                try:
                    conn.request('GET', '/pytunia-ondemand/' + sha, headers=headers)
                except socket.error as e:
                    print 'Socket error:', e
                    yield None, None, None, None
                    return
                status = conn.getresponse().status

                # only proceed on 404, i.e. no test of this sha exists
                if status == 401 or status == 403:
                    raise Exception('Authentication to builder failed')
                elif status < 400:
                    continue
                elif status != 404:
                    raise Exception('Unable to reach builder, error ' + status + ' occurred')

                yield user, repo, sha, doc
            except TypeError as e:
                print 'TypeError', e, pr
                pass
            except socket.error as e:
                print 'socket.error in MergedPytuniaSubmitter post', e
                pass

    @staticmethod
    def set_commit_status(user, repo, sha, status, description, target_url, oauth_token):
        url = '/repos/%s/%s/statuses/%s' % (user, repo, sha)
        conn = httplib.HTTPSConnection('api.github.com')
        headers = {'User-agent': config.user_agent}
        params = {'access_token': oauth_token}
        data = {
            'state': status,
            'target_url': target_url,
            'description': description
        }
        try:
            req = conn.request('POST', url + '?' + urllib.urlencode(params), json.dumps(data), headers=headers)
        except socket.error as e:
            print 'socket.error:', e
            return None, None
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
        headers = {'User-agent': config.user_agent}

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

        # size check task document
        sizecheck = {
            '_id': uuid.uuid4().get_hex(),
            'type': 'task',
            'name': 'size',
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

        docs.append(sizecheck)

        # invalid character check task document
        charcheck = {
            '_id': uuid.uuid4().get_hex(),
            'type': 'task',
            'name': 'chartest',
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

        docs.append(charcheck)

        # get task names with github api
        params = {'access_token': self.oauth_token} if self.oauth_token else {}
        params['recursive'] = 1

        tree_base_url = '/repos/%s/git/trees/' % doc['full_name']

        conn = httplib.HTTPSConnection('api.github.com')
        try:
            req = conn.request('GET', tree_base_url + sha + '?' + urllib.urlencode(params), headers=headers)
        except socket.error as e:
            print 'socket.error:', e
            return
        resp = conn.getresponse()
        data = resp.read()
        try:
            tree = json.loads(data)['tree']
        except ValueError:
            print 'ValueError:', data
            return

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
        conn, path, headers = tools.make_connection(self.db_url, headers=headers)
        try:
            conn.request('POST', '/%s/_bulk_docs' % path, docs_json, headers)
        except socket.error as e:
            print 'socket.error:', e
            return None, None
        response = conn.getresponse()

        user, repo = doc['full_name'].split('/')
        status = 'pending'
        url = self.results_base_url + sha
        description = 'Build %s started' % sha[:7]
        code, body = PullRequestWatcher.set_commit_status(config.user, repo, sha, status, description, url, self.oauth_token)
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

