from handler import Handler

class Printer(Handler):
    '''print the document'''
    def __init__(self):
        pass
    def handle(self, doc):
        print doc

