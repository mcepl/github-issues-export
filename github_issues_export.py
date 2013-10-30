#!/usr/bin/python
# -*- coding: utf-8 -*-
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the original
# work is properly attributed to Matěj Cepl.
# The name of Matěj Cepl may be used to endorse or promote
# products derived from this software without specific prior
# written permission.
# This software is provided by Matěj Cepl "AS IS" and without any
# express or implied warranties.

from ConfigParser import SafeConfigParser
from xml.etree import ElementTree as et
import urllib2
import json
import argparse
import datetime
import dateutil.parser
import getpass
import logging
import os.path
logging.basicConfig(format='%(levelname)s:%(funcName)s:%(message)s',
                    level=logging.INFO)

CLOSING_MESSAGE = """It is necessary to fix all email addresses
to correspond to bugzilla users.

Also, for importxml.pl to succeed you have to have switched on
 * move-enabled
 * moved-default-product
 * moved-default-component
"""


def _xml_indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem) != 0:
        if not (elem.text and elem.text.strip()):
            elem.text = i + "  "
        for e in elem:
            _xml_indent(e, level + 1)
        if not (e.tail and e.tail.strip()):
            e.tail = i
    else:
        if level and not(elem.tail and elem.tail.strip()):
            elem.tail = i


def load_default_configuration():
    config = {}
    conf_pars = SafeConfigParser({
        'user': getpass.getuser(),
        'password': ''
        #'api_key': None
    })
    conf_pars.read(os.path.expanduser("~/.githubrc"))
    config['git_user'] = conf_pars.get('github', 'user')
    config['git_password'] = conf_pars.get('github', 'password')
    #config['git_api_token'] = conf_pars.get('github', 'api_key')

    desc = """Export issues from a Github Issue Tracker.
           The result is file which can be imported into Bugzilla
           with importxml.pl."""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("-u", "--github_user", metavar="USER",
                        action="store", dest="github_user", default=None,
                        help="GitHub user name")
    parser.add_argument("-w", "--github_password", metavar="PASSW",
                        action="store", dest="github_password", default=None,
                        help="GitHub password")
    parser.add_argument("-b", "--be", required=False,
                        action="store_true", dest="bugseverywhere",
                        default=False,
                        help="Whether to generate BE compliant output")
    parser.add_argument("-p", "--product", required=False,
                        action="store", dest="bz_product", default=None,
                        help="Bugzilla product name")
    parser.add_argument("-c", "--component", required=False,
                        action="store", dest="bz_component", default=None,
                        help="Bugzilla user name")
    parser.add_argument("repo", nargs="?",
                        help="name of the github repo")
    options = parser.parse_args()

    if options.github_user:
        config['git_user'] = options.github_user
    if options.github_password:
        config['git_password'] = options.github_password

    config['repo'] = options.repo
    config['bz_product'] = options.bz_product
    config['bz_component'] = options.bz_component
    config['be'] = options.bugseverywhere

    return config


def add_subelement(bug, iss, iss_attr, trg_elem, convert=None):
    if (iss_attr in iss) and (iss[iss_attr] is not None):
        if convert:
            value = convert(iss[iss_attr])
        else:
            value = iss[iss_attr]
        logging.debug("iss_attr = %s, value = %s", iss_attr, value)
        et.SubElement(bug, trg_elem).text = value


def make_bz_comment(body, who, when):
    """
    <!ELEMENT long_desc (who, bug_when, work_time?, thetext)>
    <!ATTLIST long_desc
          encoding (base64) #IMPLIED
          isprivate (0|1) #IMPLIED
    >
    """
    out = et.Element("long_desc", attrib={'isprivate': '0'})
    et.SubElement(out, "who").text = who
    et.SubElement(out, "bug_when").text = when
    et.SubElement(out, "thetext").text = body
    return out


def make_be_comment(body, who, when):
    out = et.Element("comment")
    et.SubElement(out, "author").text = who
    et.SubElement(out, "date").text = when
    et.SubElement(out, "content-type").text = "text/plain"
    et.SubElement(out, "body").text = body
    return out


def format_bz_time(in_time):
    """
    in_time is ISO time
    example: "2012-02-23T22:09:58Z"
    """
    dt = dateutil.parser.parse(in_time)
    return dt.strftime("%Y-%m-%d %H:%M:%S %z")


def format_be_time(in_time):
    """
    in_time is ISO time
    example: "2012-02-23T22:09:58Z"
    """
    logging.debug("in_time = %s", in_time)
    dt = dateutil.parser.parse(in_time)
    logging.debug("dt = %s", dt)
    out = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
    logging.debug("out = %s, out")
    return out


def file_bugeverywhere_issue(cnf, iss):
    bug = et.Element("bug")

    add_subelement(bug, iss, u"created_at", "created", format_be_time)
    add_subelement(bug, iss, u"title", "summary")
    add_subelement(bug, iss, u"state", "status")
    add_subelement(bug, iss, u"assignee", "assigned")

    if (u'user' in iss) and (iss[u'user'] is not None):
        new_elem = et.Element("reporter")
        user_login = iss[u"user"][u"login"]
        new_elem.text = user_login
        bug.append(new_elem)
        new_elem = et.Element("creator")
        new_elem.text = user_login
        bug.append(new_elem)

    if u'body' in iss:
        bug.append(make_be_comment(iss[u"body"],
                                   iss[u"user"][u"login"],
                                   format_be_time(iss[u"created_at"])))

    for comment in get_comments(cnf['git_user'], cnf['git_password'],
                                cnf['repo'], iss[u"number"]):
        bug.append(make_be_comment(comment[u"body"],
                   comment[u"user"][u"login"],
                   format_be_time(comment[u"updated_at"])))

    return bug


def file_bugzilla_issue(cnf, iss):
    """
    Generate XML artifact with the issue

    """
    me_user = '%s@github.com' % cnf['git_user']
    labels = ""
    if len(iss[u"labels"]) > 0:
        labels = str(iss[u"labels"])
    created_at = format_bz_time(iss[u"created_at"])
    updated_at = format_bz_time(iss[u"updated_at"])
    if iss[u"closed_at"] and (iss[u"closed_at"] > iss[u"updated_at"]):
        closed_at = format_bz_time(iss[u"closed_at"])
    else:
        closed_at = updated_at
    status_conversion = {
        'open': 'NEW',
        'closed': 'RESOLVED'
    }

    issue_xml = et.Element("bug")
    et.SubElement(issue_xml, 'bug_id').text = str(iss[u"number"])
    et.SubElement(issue_xml, 'creation_ts').text = created_at
    et.SubElement(issue_xml, 'short_desc').text = iss[u"title"]
    et.SubElement(issue_xml, 'delta_ts').text = closed_at
    et.SubElement(issue_xml, 'reporter_accessible').text = '1'
    et.SubElement(issue_xml, 'cclist_accessible').text = '1'
    # FIXME ????
    et.SubElement(issue_xml, 'classification_id').text = ''
    # FIXME ??? same as product in RH BZ
    et.SubElement(issue_xml, 'classification').text = ''
    et.SubElement(issue_xml, 'product').text = cnf['bz_product']
    et.SubElement(issue_xml, 'component').text = cnf['bz_component']
    # there are no versions in github ... BTW, BIG MISTAKE
    et.SubElement(issue_xml, 'version').text = '0.0'
    et.SubElement(issue_xml, 'rep_platform').text = ''
    et.SubElement(issue_xml, 'op_sys').text = ''
    et.SubElement(issue_xml, 'bug_status').text = \
        status_conversion[iss[u"state"]]
    et.SubElement(issue_xml, 'status_whiteboard').text = ", ".join(labels)
    et.SubElement(issue_xml, 'priority').text = ''
    et.SubElement(issue_xml, 'bug_severity').text = ''
    # FIXME et.SubElement(issue_xml, 'votes').text = iss[u"votes"]
    et.SubElement(issue_xml, 'everconfirmed').text = ''
    et.SubElement(issue_xml, 'reporter').text = iss[u"user"][u"login"]
    et.SubElement(issue_xml, 'assigned_to').text = me_user

    issue_xml.append(make_bz_comment(iss[u"body"], iss[u"user"][u"login"],
                                     created_at))
    for comment in get_comments(cnf['git_user'], cnf['git_password'],
                                cnf['repo'], iss[u"number"]):
        issue_xml.append(make_bz_comment(comment[u"body"],
                                         comment[u"user"][u"login"],
                         format_bz_time(comment[u"updated_at"])))

    all_additional_items = ""
    # FIXME
    # for item in ("position", "diff_url", "patch_url", "pull_request_url"):
    #     all_additional_items += "%s:%s\n" % (item, getattr(iss, item))
    if len(all_additional_items.strip()) > 0:
        issue_xml.append(make_bz_comment(all_additional_items,
                         me_user, format(datetime.datetime.now())))

    return issue_xml


def get_comments(gh_user, gh_passw, repo, isno):
    API_URL = "https://api.github.com/repos/%s/issues/%d/comments"
    gh_url = API_URL % (repo, isno)

    req = urllib2.Request(gh_url)

    password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, gh_url, gh_user, gh_passw)

    auth_handler = urllib2.HTTPBasicAuthHandler(password_manager)
    opener = urllib2.build_opener(auth_handler)
    urllib2.install_opener(opener)
    handler = urllib2.urlopen(req)

    if handler.getcode() == 200:
        return json.loads(handler.read())

    raise IOError("GitHub issue list inaccessible")


def get_issues(gh_user, gh_passw, repo, state):
    """
    Get a list of issues for the particular repo from GitHub and return list.

    @param gh_user String with Github user
    @param gh_passw String with Github password
    @param repo name of the repository in form user/name
    @param state either "open" or "closed"
    @return list of dicts with issues
    """
    API_URL = "https://api.github.com/repos/%s/issues?state=%s"
    gh_url = API_URL % (repo, state)

    req = urllib2.Request(gh_url)

    password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, gh_url, gh_user, gh_passw)

    auth_handler = urllib2.HTTPBasicAuthHandler(password_manager)
    opener = urllib2.build_opener(auth_handler)
    urllib2.install_opener(opener)
    handler = urllib2.urlopen(req)

    if handler.getcode() == 200:
        return json.loads(handler.read())

    raise IOError("GitHub issue list inaccessible")


def main(conf):
    """
    Export your open github issues into a csv format for
    pivotal tracker import
    """

    if conf['be']:
        out_xml = et.fromstring("""<be-xml>
            <version>
                <tag>bf52e18a</tag>
                <committer>W. Trevor King</committer>
                <date>2011-05-25</date>
                <revision>bf52e18aad6e0e8effcadc6b90dfedf4d15b1859</revision>
            </version>
        </be-xml>""")
    else:
        out_xml = et.Element("bugzilla", attrib={
            'version': '3.4.14',
            'urlbase': 'http://github.com',
            'maintainer': 'mcepl@redhat.com',
            # FIXME ^^^
            'exporter': '%s@github.com' % conf['git_user']
        })

    for state in ('open', 'closed'):
        for issue in get_issues(conf['git_user'], conf['git_password'],
                                conf['repo'], state=state):
            if conf['be']:
                subelement_xml = file_bugeverywhere_issue(conf, issue)
            else:
                subelement_xml = file_bugzilla_issue(conf, issue)
            out_xml.append(subelement_xml)

    _xml_indent(out_xml)
    print et.tostring(out_xml, "utf-8")

    if not conf['be']:
        logging.info(CLOSING_MESSAGE)

if __name__ == '__main__':
    config = load_default_configuration()
    main(config)
