from handler import Handler

from ..log import log
from .. import yelling

class Emailer(Handler):
    '''generate and send a commit summary email'''
    def __init__(self, recipients, sender=None):
        self.recipients = recipients
        self.sender = sender

    def handle(self, doc):
        subject = '%i commit(s) pushed to %s (%s)' % (len(doc['commits']), doc['repository']['name'], doc['ref'])

        body = \
'''%i commit(s) pushed to %s (on ref %s)
Repository URL: %s
Date: %s

''' % (len(doc['commits']), doc['repository']['name'], doc['ref'], doc['repository']['url'], 1)

        for c in doc['commits']:
            commit_body = '-' * 40 + '\n'
            commit_body += \
'''ID: %s
Timestamp: %s
Author: %s (%s)
Full diff: %s
Message:

%s

''' % (c['id'], c['timestamp'], c['author']['name'], c['author']['email'], c['url'], c['message'])

            body += commit_body

        yelling.email(self.recipients, subject, body, self.sender)
        log.write('Emailer: sent email "%s" to %i recipients' % (subject, len(self.recipients)))

