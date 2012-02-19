#!/usr/bin/env python

import sys
import json
from cgi import parse_qs # need?
from wsgiref.simple_server import make_server

import repoman.settings
import repoman.handlers as h

# handlers for various repos (identified by name)
handlers = {'github': [h.print_doc, h.email, h.pytunia],
            'rat': [h.print_doc, h.email, h.pytunia, h.mirror],
            'rat-doc': [h.print_doc, h.email, h.docbuild, h.mirror],
            'rat-tools': [h.print_doc, h.mirror]}

def main(env, start_response):
    if env['REQUEST_METHOD'] != 'POST':
        status = '501 NOT IMPLEMENTED'
    else:
        request_length = int(env['CONTENT_LENGTH'])
        request_body = env['wsgi.input'].read(request_length)
        doc = json.loads(request_body)

        repo_name = doc['repository']['name']
        for handler in handlers[repo_name]:
            print 'Handler:', handler
            handler(doc)

    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return []

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage:', sys.argv[0], '<port>'
        sys.exit(1)

    port = int(sys.argv[1])
    httpd = make_server('', port, main)

    print 'repoman starting on localhost:%i' % port
    httpd.serve_forever()

