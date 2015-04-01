import httplib
import base64
import re

def make_connection(url, headers={}):
    '''make an http(s) connection based on a url string. includes basic
    authentication.
    '''
    if url[-1] != '/':
        url += '/'
    match = re.match(r'((?P<protocol>.+):\/\/)?((?P<user>.+):(?P<pw>.+)?@)?(?P<url>.+)', url)
    if not match:
        raise KeyError('Error in URL string')

    host, path = match.group('url').split('/', 1)
    if match.groups('protocol') == 'https':
        conn = httplib.HTTPSConnection(host)
    else:
        conn = httplib.HTTPConnection(host)

    hdrs = {'Content-type': 'application/json'}
    hdrs.update(headers)
    if match.group('user'):
        auth_string = base64.encodestring('%s:%s' % (match.group('user'), match.group('pw')))[:-1]
        hdrs['Authorization'] = 'Basic %s' % auth_string

    return conn, path, hdrs

