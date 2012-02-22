#!/usr/bin/env python

import sys
import json
from cgi import parse_qs # need?
from wsgiref.simple_server import make_server

from repoman.log import log
import config

def main(env, start_response):
    if env['REQUEST_METHOD'] != 'POST':
        status = '501 NOT IMPLEMENTED'
    else:
        request_length = int(env['CONTENT_LENGTH'])
        request_body = parse_qs(env['wsgi.input'].read(request_length))

        doc = json.loads(request_body['payload'][0])

        repo_name = doc['repository']['name']
        for handler in config.handlers[repo_name]:
            handler.handle(doc)

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

    log.write('repoman starting on localhost:%i' % port)
    httpd.serve_forever()

