repoman
=======
handle changes to a [github](http://www.github.com) repository.

github's WebHook URLs service hook will POST some JSON to a given URL every time you push to a repository. repoman is a little Python WSGI server that listens for these requests and executes a series of actions.

These actions are written as `Handler` subclasses, and there are four handlers built in:

1. Printer: Print commit data to stdout
2. Emailer: Send a commit summary email
3. PytuniaSubmitter: Upload some tests to a [pytunia](http://github.com/mastbaum/pytunia) instance
4. Repeater: Pass the commit data along to another URL

Handlers are defined on a per-repository basis in a Python configuration file. An example is provided in `bin/`.

Extra Tools
-----------
There are extra, standalone Python WSGI applications also included:

1. `mirror` (in `bin/mirror`): clone/pull the repository to a local directory, creating a mirror
2. `docbuild` (in `bin/docbuild`): build TeX documentation (easily modified to run any script on the repo)

A server may run all three -- with two `Repeater` handlers passing push data along to the `mirror` and `docbuild` instances:

```
                   mirror
         |fire|     /|\
github ---------> repoman
         |wall|     \|/
                  docbuild
```

Or just repoman (perhaps with custom `Handler`s), or just `mirror`, etc.

### Pull Request Watcher ###
A third, non-WSGI tool `pullci` is included, which triggers actions (handlers) based on open pull requests.

As provided, `pullci` will start `pytunia` build tests of open pull requests. Specifically, these build tests will check out the HEAD of the request, attempt merge in the base ref, and run tests on that. Given an OAuth token, `pullci` will set the status of the HEAD commit to "pending" using the GitHub [commit status API](https://github.com/blog/1227-commit-status-api). `pytunia` (or your own tool) is responsible for setting the final status.
