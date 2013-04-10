#!/usr/bin/env python

import sys
import os
import cgi
import subprocess
import shutil
import json

import requests
import getpass

base_path = os.path.abspath(os.path.split(__file__)[0])
org_name = "w3c"
repo_name = "web-platform-tests"
username = "jgraham"

class MasterCheckout(object):
    def __init__(self, path=base_path):
        self.path = path

    @classmethod
    def create(cls, remote):
        path = base_path
        rv = cls(path)
        git_command("clone", remote, os.path.join(path, "tmp"), cwd=path)
        os.rename(os.path.join(path, "tmp", ".git"), os.path.join(path, ".git"))
        git_command("reset", "--hard", "HEAD")
        git_command("config", "--add", "remote.origin.fetch", "+refs/pull/*/head:refs/remotes/origin/pr/*", cwd=path)
        git_command("fetch", "origin", cwd=path)
        return rv

    def update(self):
        git_command("fetch", "origin", cwd=self.path)
        git_command("checkout", "origin/master")

class PullRequestCheckout(object):
    def __init__(self, number, path):
        self.number = number
        self.path = path

    @classmethod
    def fromNumber(cls, number):
        path = os.path.join(base_path, "submissions", str(number))
        if os.path.exists(path):
            return cls(path)

    @classmethod
    def create(cls, number):
        path = os.path.join(base_path, "submissions", str(number))
        if not os.path.exists(path):
            os.mkdir(path)
        rv = cls(number, path)
        git_command("clone", "--no-checkout", base_path, path, cwd=path)
        rv.update()
        return rv

    def delete(self):
        shutil.rmtree(self.path)

    def update(self):
        git_command("fetch", "origin", "refs/remotes/origin/pr/%i:pr" % self.number, cwd=self.path)
        git_command("checkout", "pr", cwd=self.path)

def git_command(command, *args, **kwargs):
    cwd = kwargs.get("cwd", base_path)
    no_throw = kwargs.get("no_throw", False)
    cmd = ["git", command] + list(args)
    print >> sys.stderr, repr(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        if no_throw:
            return False
        else:
            raise IOError(stderr)
    return True

def processPullRequest(data):
    action = data["action"]

    action_handlers = { "opened": pullRequestOpened,
                        "reopened": pullRequestOpened,
                        "closed": pullRequestClosed,
                        "synchronize": pullRequestSynchronize }
    action_handlers["action"](data["number"])

def pullRequestOpened(number):
    PullRequestCheckout.create(number)

def pullRequestClosed(number):
    PullRequestCheckout.fromNumber(number).delete()

def pullRequestSynchronize(number):
    PullRequestCheckout.fromNumber(number).update()

def processPush(data):
    checkout = MasterCheckout()
    checkout.update()

def main():
    data = sys.stdin.read()
    if data:
        data = json.loads(data)
        if "pull_request" in data:
            return processPullRequest(data)
        elif "commits" in data:
            processPush(data)
    print "Content-Type: text/plain"
    print "\r"
    print "Success"

def setup():
    if not os.path.exists(os.path.join(base_path, "submissions")):
        os.mkdir(os.path.join(base_path, "submissions"))
    if not os.path.exists(".git"):
        MasterCheckout.create("git://github.com/%s/%s.git" % (org_name, repo_name))
    pull_requests = requests.get("https://api.github.com/repos/%s/%s/pulls" % (org_name, repo_name), auth=(username, getpass.getpass())).json()
    open_numbers = [item["number"] for item in pull_requests if item["state"] == "open"]
    for number in open_numbers:
        pull_request = PullRequestCheckout.create(number)

if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup()
    else:
        main()
