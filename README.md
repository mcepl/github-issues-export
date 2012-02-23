Script to liberate issues from github issues in case you would like to have
your data free.

The resulting XML file can be imported to bugzilla with importxml.pl, and although
it is not perfect (patches and pull requests welcome!), I don't think there is any
data loss and it can be cleaned up in the Bugzilla after import.

Requires python-github2 (either from https://github.com/ask/python-github2 or as PyPI
package github2).