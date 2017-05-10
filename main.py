from mastodon import Mastodon
from mastodon import streaming
import tweepy
from tweepy import OAuthHandler
import yaml
import os
import time
import threading
import re
import random
import csv
import sys


try:
    with open ('lists.csv', 'r') as incsv:
        reader = csv.reader(incsv)
        alllists = []
        for x in reader:
            alllists.append(x)
        # Timestamps of all toots younger than one hour
        lasttoots = [float(time) for time in alllists[0]]
        # Timestamps of all random toots younger than 30 minutes
        lastrandomtoot = [float(time) for time in alllists[1]]

    if os.path.isfile('configuration.local.yaml'):
        with open ('configuration.local.yaml', 'r') as f:
            config = yaml.load(f)
    else:
        with open ('configuration.yaml', 'r') as f:
            config = yaml.load(f)

    consumer_key = config['TwitterAPI']['ConsumerKey']
    consumer_secret = config['TwitterAPI']['ConsumerSecret']
    access_token = config['TwitterAPI']['AccessToken']
    access_secret = config['TwitterAPI']['AccessSecret']
    masto_clientid = config['MastodonAPI']['ClientID']
    masto_clientsecret = config['MastodonAPI']['ClientSecret']
    masto_access_token = config['MastodonAPI']['AccessToken']
    mastodonmail = config['MastodonAPI']['MastodonMail']
    mastodonpw = config['MastodonAPI']['MastodonPW']


    class MeinStreamListener(streaming.StreamListener):
        def __init__(self, tooter):
            self.answerrequest = tooter

        def on_update(self, status):
            print('Update')

        def on_notification(self, notification):
            if notification['type'] == 'mention':
                self.answerrequest.inqueue.append({'when': notification['created_at'], 'postid': notification['status']['id'], 'postcontent': notification['status']['content'], 'sender': notification['status']['account']['acct'], 'senderid': notification['status']['account']['id']})
                print('Status zur Warteschlange hinzugefügt')
                self.answerrequest.queuetoot()


        def on_delete(self, status_id):
            print('Delete')

    class RequestetToots():

        def __init__(self, twitterapi):
            self.twitterapi = twitterapi
            self.inqueue = []
            self.outqueue = []
            self.availabletrends = [{'woeid': place['woeid'], 'name': place['name']} for place in self.twitterapi.trends_available()]

        def queuetoot(self):
            while len(self.inqueue) > 0:
                toanswer = self.inqueue.pop(0)
                keywords = self.findkeyword(toanswer['postcontent'])
                if len(keywords) == 0:
                    self.outqueue.append("Hey {} I'm sure there is a lot of annoying stuff happening on Twitter right now. But there are no Trends for any of the keywords you've provided me.".format(toanswer['sender']))
                    return
                for keyword in keywords:
                    trends_and_date = self.gettrends(self.getwoeid(keyword))
                    self.outqueue.append(self.buildtoot(keyword, trends_and_date, toanswer['sender']))
                    print('Requestet Trend appended to outgoing Queue')
                    return

        def findkeyword(self, content):
            return [word for word in re.sub('<[^<]+?>|[#,.!?:\(\)<>]', '', content).split() if word in [dic['name'] for dic in self.availabletrends]]


        def gettrends(self, woeid):
            trendsjson = self.twitterapi.trends_place(woeid)
            trends = []
            for dic in trendsjson:
                for trend in dic['trends']:
                    trends.append((trend['name'], trend['tweet_volume']))
            date = trendsjson[0]['created_at']
            return(trends), date
            #return [(trend['name'], trend['tweet_volume']) for trend in dic['trends'] for dic in trendsjson]

        def getwoeid(self, keyword):
            woeid = [place['woeid'] for place in self.availabletrends if place['name'].lower() == keyword.lower()]
            return woeid[0]

        def buildtoot(self, placename, trends_and_date, sender):
            trends = trends_and_date[0]
            created_at = trends_and_date[1]
            if sender == False:
                tootbody = 'Probably annoying stuff, going on in Twitter-{}:\n'.format(placename)
                end = '\n\nSource: Twitter Trends {}, retrieved at {} GMT\nAsk me for more annoying Twitter-Stuff from anywhere on the world.\n#TwitterButBetter'.format(placename, created_at)
            else:
                tootbody = 'Hey @{}, You asked for probably annoying stuff, going on in Twitter-{}:\n'.format(sender, placename)
                end = '\n\nSource: Twitter Trends {}, retrieved at {} GMT\n#TwitterButBetter'.format(placename, created_at)
            while len(tootbody) + len(end) <= 500:
                trend = trends.pop(0)
                if trend[1] == None:
                    tootbody += '{} \n'.format(trend[0])
                else:
                    tootbody += '{} | {} Tweets \n'.format(trend[0], str(trend[1]))
            if len(tootbody) + len(end) >= 500:
                tootbody = tootbody[:tootbody.rfind('\n')]
                tootbody = tootbody[:tootbody.rfind('\n')]
            tootbody += end
            return tootbody

    def tootit():
        allyoungerthanonehour = False
        # while-loop to update the list of toots last hour
        while allyoungerthanonehour == False:
            if len(lasttoots) == 0:
                tootslasthour = len(lasttoots)
                allyoungerthanonehour = True
            elif time.time() - lasttoots[0] > 3600: #3600
                lasttoots.pop(0)
            else:
                tootslasthour = len(lasttoots)
                allyoungerthanonehour = True
        # if there where less than 149 toots last hour: toot. Either answer an toot, or post random Twitter-Trends.
        if tootslasthour < 149:
            print('{} toots last hour. I\'ll keep on tooting....'.format(tootslasthour))
            if len(requests.outqueue) > 0:
                print('..a reply to an request.')
                toot = requests.outqueue.pop(0)
                mastodonapi.toot(toot)
                print('Tooooooot!')
                lasttoots.append(time.time())
            elif len(lastrandomtoot) == 0 or time.time() - lastrandomtoot[0] > 1800:
                print('..a random Twitter-Trend')
                try:
                    lastrandomtoot.pop(0)
                except:
                    pass
                toot = getrandomtrend()
                mastodonapi.toot(toot)
                print('Tooooooot!')
                lasttoots.append(time.time())
                lastrandomtoot.append(time.time())
            else:
                print('..nothing. No requests...')
                print('Next Random Trend in {}'.format(1800 - (time.time() - lastrandomtoot[0])))
        else:
            print('{} toots last hour. I\'ll stop tooting for know.'.format(tootslasthour))
        threading.Timer(15, tootit).start() # starts every after 10 seconds.
        return

    def getrandomtrend():
        alltrends = requests.availabletrends
        trend = random.choice(alltrends)
        trends_and_date = requests.gettrends(trend['woeid'])
        toot = requests.buildtoot(trend['name'], trends_and_date, False)
        return toot


    # SetUp TwitterAPI
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)
    twitterapi = tweepy.API(auth)

    # SetUp MastodonAPI
    #mastodon = Mastodon(client_id = 'annoyingtwittertrends_clientcred.txt',access_token = 'annoyingtwittertrends_usercred.txt')
    mastodonapi = Mastodon(client_id = masto_clientid, client_secret = masto_clientsecret ,access_token = masto_access_token)
    mastodonapi.log_in(mastodonmail, mastodonpw ,to_file = 'twittertrends_usercred.txt')



    requests = RequestetToots(twitterapi)
    # Start Toot Function
    tootit()
    # Listen to Mastodon Stream
    streamlistener = MeinStreamListener(requests)
    stream = mastodonapi.user_stream(listener = streamlistener)

except KeyboardInterrupt:
    mastodonapi.toot('Going offline for a while! See you later:-*')
    with open ('lists.csv', 'w') as outcsv:
        writer = csv.writer(outcsv)
        writer.writerow(lasttoots)
        writer.writerow(lastrandomtoot)
    print('Saved Tables...')
    print('Bye!')
    sys.exit(0)
