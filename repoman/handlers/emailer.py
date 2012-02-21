from handler import Handler

#import yelling

class Emailer(Handler):
    '''generate and send a commit summary email'''
    def __init__(self):
        # yelling settings: smtp server, etc.
        pass

    def handle(self, doc):
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

        print body
        #FIXME yelling.email

