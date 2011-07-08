#!/usr/bin/python2.5

"""Tablecat is a twitter bot that supports multiple nicks and servers, and is
configurable through YAML files.
"""

import logging
import optparse
import os
import re
import sys
import yaml

from oyoyo import helpers
from oyoyo.client import IRCApp, IRCClient
from oyoyo.cmdhandler import DefaultCommandHandler
import twitter as twitter_mod
import backcompat


Config = backcompat.namedtuple('Config', 'host nick port channels twitters')
Twitter = backcompat.namedtuple('Account', 'channel username cons_key cons_secret '
                                 'token_key token_secret')

class ConfigException(Exception):
    pass


class BotClient(IRCClient):
    def __init__(self, conf_file):
        conf_yaml = yaml.load(open(conf_file))

        # First load the twitters section into specific Twitter instances
        if 'twitters' not in conf_yaml:
            raise ConfigException('"twitter" section not found in file: "%s"' % conf_file)

        twitters = []
        for twitter_yaml in conf_yaml['twitters']:
            try:
                twitter = Twitter(twitter_yaml['channel'], twitter_yaml['username'],
                                  twitter_yaml['cons_key'], twitter_yaml['cons_secret'],
                                  twitter_yaml['token_key'], twitter_yaml['token_secret'])
                twitters.append(twitter)
            except KeyError, e:
                raise ConfigException('"%s" key missing in "twitters" section of file: "%s"' % (e.args[0], conf_file))

        # Now roll twitters and everything else into one self.config object
        try:
            self.config = Config(conf_yaml['host'], conf_yaml['nick'],
                                 conf_yaml['port'] if 'port' in conf_yaml else 6667,
                                 conf_yaml['channels'],
                                 twitters)
        except KeyError, e:
            raise ConfigException('"%s" key missing in file: "%s"' % (e.args[0], conf_file))

        # Instantiate twitter API instances
        twitter_apis = {}
        for twitter in twitters:
            twitter_apis[twitter.username] = twitter_mod.Api(consumer_key=twitter.cons_key,
                                                             consumer_secret=twitter.cons_secret,
                                                             access_token_key=twitter.token_key,
                                                             access_token_secret=twitter.token_secret)
        self.twitter_apis = twitter_apis
       
        # Call super init
        IRCClient.__init__(self, BotHandler, host=self.config.host, port=self.config.port,
                           nick=self.config.nick, connect_cb=self.connect_cb)

    def connect_cb(self, unusued_cli):
        for channel in self.config.channels:
            helpers.join(self, channel)

        
class BotHandler(DefaultCommandHandler):
    def privmsg(self, prefix, chan, msg):
        # Check for !tweet command
        match = re.match('\!tweet (.*)', msg)
        if match:
            status = match.group(1).strip()

            for twitter in self.client.config.twitters:
                if twitter.channel == chan:
                    api = self.client.twitter_apis[twitter.username]

                    sent = False
                    try:
                        api.PostUpdate(status)
                        sent = True
                    except twitter_mod.TwitterError, e:
                        print 'Error posting status:', e
                        
                    if sent:
                        helpers.msg(self.client, chan, 'It has been tweeted. http://twitter.com/%s' % twitter.username)
                        print '%s responded to %s (%s) posting %s ' % (twitter.username, prefix, chan, repr(msg))
        
        match = re.match('\!soapself (.*)', msg)
        if match:
            status = match.group(1).strip()
            helpers.msg(self.client, 'nickserv', 'identify omlette')
            helpers.msg(self.client, chan, 'Si, Capitan!')
            print 'Authing Self'

def main():
    # Define parser options
    parser = optparse.OptionParser()
    parser.add_option('-L', '--log-level', dest='log_level',
                      help='Override the default logging level. Valid: debug, info, warning error, critical')
    parser.add_option('-c', '--conf-dir', dest='conf_dir',
                      default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'confs'),
                      help='Override the default conf directory.')
    options, args = parser.parse_args()

    # Set the default logging level, if valid
    if options.log_level is not None:
        LEVELS = {'debug': logging.DEBUG,
                  'info': logging.INFO,
                  'warning': logging.WARNING,
                  'error': logging.ERROR,
                  'critical': logging.CRITICAL}
        level = LEVELS.get(options.log_level, logging.NOTSET)
        logging.basicConfig(level=level)

    # Check conf dir exists and retrieve list of yaml files
    if not os.path.isdir(options.conf_dir):
        print 'Config dir "%s" does not exist or is not a directory' % options.conf_dir
        sys.exit(1)

    conf_files = []
    for fname in os.listdir(options.conf_dir):
        if fname.endswith('.yaml'):
            conf_files.append(os.path.join(options.conf_dir, fname))

    # Load one client for each yaml file, and start
    app = IRCApp()
    for conf_file in conf_files:
        app.addClient(BotClient(conf_file))
    app.run()


if __name__ == '__main__':
    main()
    


