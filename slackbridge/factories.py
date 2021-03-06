from twisted.internet import reactor
from twisted.internet import ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log

from slackbridge.bots import BridgeBot
from slackbridge.bots import IRCBot
from slackbridge.bots import UserBot
from slackbridge.utils import IRC_HOST
from slackbridge.utils import IRC_PORT


class BotFactory(ReconnectingClientFactory):

    def clientConnectionLost(self, connector, reason):
        log.err('Lost connection.  Reason: {}'.format(reason))
        super().clientConnectionLost(connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.err('Connection failed. Reason: {}'.format(reason))
        super().clientConnectionFailed(connector, reason)


class BridgeBotFactory(BotFactory):

    def __init__(self, slack_client, bridge_nick, nickserv_pw, slack_uid,
                 channels, users):
        self.slack_client = slack_client
        self.slack_uid = slack_uid
        self.bridge_nickname = bridge_nick
        self.nickserv_password = nickserv_pw
        self.channels = channels
        self.bot_class = BridgeBot
        self.user_bots = []

        # Give all bots access to the slack userlist
        IRCBot.slack_users = users

        # Create individual user bots with their own connections to the IRC
        # server and their own nicknames
        for user in users:
            self.instantiate_bot(user)

    def buildProtocol(self, addr):
        p = BridgeBot(
            self.slack_client,
            self.bridge_nickname,
            self.nickserv_password,
            self.slack_uid,
            self.channels,
            self.user_bots,
        )
        p.factory = self
        self.resetDelay()
        return p

    def add_user_bot(self, user_bot):
        self.user_bots.append(user_bot)

    def instantiate_bot(self, user):
        user_factory = UserBotFactory(
            self, user,
            self.channels,
            self.bridge_nickname,
            self.nickserv_password,
        )
        reactor.connectSSL(
            IRC_HOST, IRC_PORT, user_factory, ssl.ClientContextFactory()
        )


class UserBotFactory(BotFactory):

    def __init__(self, bridge_bot_factory, slack_user, channels,
                 target_group, nickserv_pw):
        self.bridge_bot_factory = bridge_bot_factory
        self.slack_user = slack_user
        self.channels = []
        self.target_group_nick = target_group
        self.nickserv_password = nickserv_pw

        for channel in channels:
            if slack_user['id'] in channel['members']:
                self.channels.append(channel)

    def buildProtocol(self, addr):
        p = UserBot(
            self.slack_user['name'],
            self.slack_user['real_name'],
            self.slack_user['id'],
            self.channels,
            self.target_group_nick,
            self.nickserv_password,
        )
        p.factory = self
        self.bridge_bot_factory.add_user_bot(p)
        self.resetDelay()
        return p
