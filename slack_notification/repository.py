import json
import requests
import re
from trac.core import *
from trac.config import Option, IntOption
from trac.versioncontrol.api import IRepositoryChangeListener, Changeset, Repository

def prepare_repositorychange_values(env, repos, changeset, action=None):
    values = dict({
        "project": env.project_name.strip(),
        "projecturl": env.project_url,
        "repos_name": repos.name,
        "repos_reponame": repos.reponame,
        "repos_id": repos.id,
        "repos": changeset.repos,
        "rev": changeset.rev,
        "revurl": env.abs_href.changeset(changeset.rev),
        "message": changeset.message,
        "author": changeset.author,
        "date": changeset.date,
        "action": action,
    })
    return values

class SlackRepositoryNotifcationPlugin(Component):
    implements(IRepositoryChangeListener)
    webhook = Option('slack', 'repo-webhook', 'https://hooks.slack.com/services/',
            doc="Incoming webhook for Slack")
    channel = Option('slack', 'repo-channel', '#Trac',
            doc="Channel name on Slack")
    username = Option('slack', 'repo-username', 'Trac-Bot',
            doc="Username of the bot on Slack notify")
    repoadd = IntOption('slack', 'repoadd', '1', doc="Turn add notification on or off (defaults on)")
    repomod = IntOption('slack', 'repomod', '0', doc="Turn modification notification on or off (defaults off)")
    authmap = Option('slack', 'authmap', '',
            doc="Map trac-authors to Name, Slack user IDs (preferred) and/or email addresses (<TracUsername>:<Name>,<@SlackUserID>,<email>;...)")

    def mapAuth(self, values):
        author = values.get('author',None)
        if not author:
            return
        # make sure author formatting is correct...
        author = re.sub(r' <.*', '', author)
        if not self.authmap:
            values['author'] = author
            return
        try:
            for am in self.authmap.strip().split(";"):
                au,ad = am.strip().split(":")
                if not au:
                    continue
                if author != au:
                    continue
                if not ad:
                    continue
                ad = ad.strip().split(",")
                if len(ad) > 1 and ad[1]:
                    author = "<%s>"%(ad[1])
                    break
                if len(ad) > 0 and ad[0]:
                    author = ad[0]
                if len(ad) > 2 and ad[2]:
                    author = "<mailto:%s|%s>"%(ad[2],author)
                break
        except Exception as err:
            self.log.warning("failed to map author: %s"%(str(err)))
        values["author"] = author

    def notify(self, values):
        self.log.warning("slack notify values: %s"%(str(values)))
        self.mapAuth(values)
        template = u'_%(project)s_ :heavy_plus_sign: \n<%(revurl)s|r%(rev)s> was *%(action)s* by %(author)s'
        message = template % values
        # set type-specific attachements as needed
        attachments = []
        if values["message"]:
            attachments.append({
                    'title': u'Message',
                    'text': values['message']
            })
        attachments.append({
                'title': u'Date',
                'text': values['date']
        })
        attachments.append({
                'title': u'RepoName',
                'text': values['repos_reponame']
        })
        attachments.append({
                'title': u'Repos',
                'text': values['repos']
        })
        # send it all out
        data = {
            "channel": self.channel,
            "username": self.username,
            "text": message.encode('utf-8').strip(),
            "attachments": attachments
        }
        try:
            r = requests.post(self.webhook, data={"payload":json.dumps(data)})
        except requests.exceptions.RequestException as e:
            self.log.exception("Failed to post slack notification: %s" % (e))
            return False
        return True

    """
    Called after a changeset has been added to a repository.
    @param repos: 
    @param changeset: 
    """
    def changeset_added(self, repos, changeset):
        if (self.repoadd != 1):
            return
        try:
            values = prepare_repositorychange_values(self.env, repos, changeset, action="added")
            self.notify(values)
        except Exception as err:
            self.log.exception("Fail to notify slack about changeset_added: %s" % (str(err)))

    """
    Called after a changeset has been modified in a repository.
    @param repos: 
    @param changeset: 
    @param old_changeset: contains the metadata of the changeset prior to the modification,
                            None if the old metadata cannot be retrieved.
    """
    def changeset_modified(self, repos, changeset, old_changeset):
        if (self.repomod != 1):
            return
        try:
            values = prepare_repositorychange_values(self.env, repos, changeset, action="modified")
            self.notify(values)
        except Exception as err:
            self.log.exception("Fail to notify slack about changeset_modified: %s" % (str(err)))

