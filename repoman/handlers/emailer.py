from handler import Handler

from ..log import log
from .. import yelling

import time

body_template = \
'''%i commit(s) pushed to %s (on ref %s)
Repository URL: %s
Date: %s

Commit Summary
==============
%s

Commit Details
==============
%s
'''

commit_summary_template = \
'''
%s: %s
'''

commit_detail_template = \
'''
ID: %s
Timestamp: %s
Author: %s (%s)
Full diff: %s

%s

''' 

class Emailer(Handler):
    '''generate and send a commit summary email'''
    def __init__(self, recipients, sender=None):
        self.recipients = recipients
        if sender is None:
            import socket
            import getpass
            sender = '%s@%s' % (getpass.getuser(), socket.getfqdn())
        self.sender = sender

    def handle(self, doc):
        subject = '%i commit(s) pushed to %s (%s)' % (
            len(doc['commits']),
            doc['repository']['name'],
            doc['ref']
        )

        commit_summary = ''
        commit_details = ''
        for c in doc['commits']:
            leader = c['message'].split('\n')[0]
            commit_summary += commit_summary_template % (
                c['id'][:7],
                leader if len(leader) < 50 else (leader[:50] + '...')
            )

            commit_details += commit_detail_template % (
                c['id'],
                c['timestamp'],
                c['author']['name'],
                c['author']['email'],
                c['url'],
                c['message']
            )

	body = ('Subject: %s' % subject) + '\n\n' + body_template % (
            len(doc['commits']),
            doc['repository']['name'],
            doc['ref'],
            doc['repository']['url'],
            time.asctime(),
            commit_summary,
            commit_details
        )

        yelling.email(self.recipients, subject, body, self.sender)

        log.write('Emailer: sent email "%s" to %i recipients' % (
            subject,
            len(self.recipients)
        ))

