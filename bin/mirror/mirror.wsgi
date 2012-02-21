#!/usr/bin/env python

import sys
import json
from wsgiref.simple_server import make_server

import settings

def main(env, start_response):
    if env['REQUEST_METHOD'] != 'POST':
        status = '501 NOT IMPLEMENTED'
    else:
        request_length = int(env['CONTENT_LENGTH'])
        request_body = env['wsgi.input'].read(request_length)
        doc = json.loads(request_body)

        print doc

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

    print 'mirror starting on localhost:%i' % port
    httpd.serve_forever()

