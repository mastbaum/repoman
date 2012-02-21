from handler import Handler

from .. import tools

import json

class Repeater(Handler):
    '''re-post the document to another server'''
    def __init__(self, url, git_url=None):
        self.url = url
        self.git_url = git_url

    def handle(self, doc):
        if self.git_url is not None:
            doc['git_url'] = self.git_url

        conn, path, headers = tools.make_connection(self.url)
        conn.request('POST', path, json.dumps(doc), headers)
        response = conn.getresponse()

        log.write('Repeater: posted to server at %s, reponse: %s %s' % (
            self.url,
            response.status,
            response.reason
        ))

