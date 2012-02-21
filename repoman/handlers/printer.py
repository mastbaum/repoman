from handler import Handler

from ..log import log

class Printer(Handler):
    '''print the document'''
    def __init__(self):
        pass

    def handle(self, doc):
        log.write('Printer: ' + str(doc))

