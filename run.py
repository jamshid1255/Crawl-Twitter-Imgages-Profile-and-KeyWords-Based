#!/usr/bin/python3
import tweepy
import os
from tweepy import OAuthHandler
import json
import wget
import argparse
import configparser
from datetime import timezone
import sys



def parse_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    return config

def save_config(config, config_file):
    with open(config_file, 'w') as fp:
        config.write(fp)
        print('Wrote ' + config_file)
    return


def parse(cls, api, raw):
    status = cls.first_parse(api, raw)
    setattr(status, 'json', json.dumps(raw))
    return status


def init_tweepy():
    # Status() is the data model for a tweet
    tweepy.models.Status.first_parse = tweepy.models.Status.parse
    tweepy.models.Status.parse = parse
    # User() is the data model for a user profile
    tweepy.models.User.first_parse = tweepy.models.User.parse
    tweepy.models.User.parse = parse


def get_access(auth):
    # This is called if there is no access token yet in the config.cfg file.
    # This routine asks the user retrieve one from twitter.
    # Access token & secret are returned in auth.access_token{_secret}.
    try:
        redirect_url = auth.get_authorization_url()
    except tweepy.TweepError:
        print('Error! Failed to get request token.')
        sys.exit(1)

    print('Please get a PIN verifier from ' + redirect_url)
    verifier=None
    while not verifier or '\ufffc' in verifier:
        verifier = input('Verifier: ')
    try:
        auth.get_access_token(verifier)
    except tweepy.TweepError:
        print('Error! Failed to get access token.')
        sys.exit(1)


def authorise_twitter_api(config_path):
    config = parse_config(config_path)
    if not config.has_option('DEFAULT', 'consumer_key') or not config.has_option('DEFAULT', 'consumer_secret'):
        # Ooops, no config.cfg file. Need to generate one.
        print(f"{config_path} is missing consumer_key / consumer_secret.")
        print("Please register your own app at http://apps.twitter.com/.")
        consumer_key = None
        consumer_secret = None
        while not consumer_key or '\ufffc' in consumer_key:
            consumer_key = input('Consumer (API) key: ')
        config.read_string(f"[DEFAULT]\nconsumer_key = {consumer_key}")
        while not consumer_secret or '\ufffc' in consumer_secret:
            consumer_secret = input('Consumer (API) secret: ')
        config.read_string(f"[DEFAULT]\nconsumer_secret = {consumer_secret}")

    try:
        auth = OAuthHandler(config['DEFAULT']['consumer_key'], config['DEFAULT']['consumer_secret'])
    except TokenRequestDenied:
        print('Error! Failed to get API token.')
        sys.exit(1)


    if 'access_token' not in config['DEFAULT']:
        # Ask the user for an access token from Twitter
        get_access(auth)
        config['DEFAULT']['access_token'] = auth.access_token
        config['DEFAULT']['access_secret'] = auth.access_token_secret
        save_config(config, config_path)

    # Tell tweepy to use the user's access token.
    auth.set_access_token(config['DEFAULT']['access_token'], config['DEFAULT']['access_secret'])

    return auth


# It returns [] if the tweet doesn't have any media
def tweet_media_urls(tweet_status):
    # At least one image
    if 'media' in tweet_status.entities:
        # Grabbing all pictures
        media = tweet_status.extended_entities['media']

        return get_media_jpg_or_gif(media)
    else:
        return {}

def get_media_jpg_or_gif(media):

    a=[ { 'filename': f"{item['id_str']}.jpg", 
          'url': f"{item['media_url']}?format=jpg&name=large" }
        for item in media if item['type'] == 'photo' ]

    b=[ { 'filename': f"{item['id_str']}.mp4", 
          'url': f"{item['video_info']['variants'][0]['url']}" }
        for item in media
        if item['type'] == 'video' or item['type'] == 'animated_gif' ]

    for item in media:
        if item['type'] == 'photo': continue
        if item['type'] == 'animated_gif': continue
        if item['type'] == 'video': continue
        from pprint import pprint as pp
        pp("Unhandled media type")
        pp(item["type"])
    return a+b

def create_folder(output_folder):
    "Create a folder if it doesn't exist. Return modification time of .timestamp if it does."
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        timestamp = 0
    else:
        try:
            timestamp = os.stat(os.path.join(output_folder, '.timestamp')).st_mtime
        except:
            timestamp = 0
    return timestamp

def download_images(status, num_tweets, output_folder):
    timestamp = create_folder(output_folder)
    ts_file = os.path.join(output_folder, '.timestamp')
    downloaded = 0

    for tweet_status in status:
        if downloaded >= num_tweets:
            print('Stopping after downloading ' + str(num_tweets) + ' tweets.' )
            break
        created = tweet_status.created_at.strftime('%y-%m-%d at %H.%M.%S %Z')
        tweet_id = tweet_status.id_str
        full_text = tweet_status.text

        # Creation time of tweet as seconds.nanoseconds since The Epoch.
        ctime = tweet_status.created_at.timestamp() 
        ctime = float(ctime)

        if ctime < timestamp:
            # TODO: Probably ought to use the Twitter's "cursor" to request tweets newer than timestamp
            print('Stopping at ' + created + ' which is older than .timestamp' )
            return

        for media_info in tweet_media_urls(tweet_status):
            # Download each media URL, if the file doesn't exist already.
            file_name = media_info['filename']
            media_url = media_info['url']

            output_file = os.path.join(output_folder, file_name)
            if os.path.exists(output_file):
                print(f"Skipping existing file: {file_name}")
            else:
                print(media_url)
                #print(full_text)
                print(output_file)
                wget.download(media_url, out=output_file)
                downloaded += 1
                os.utime(output_file, (ctime, ctime))
                os.close(os.open(ts_file, os.O_CREAT))
    print("End of tweet statuses")

def download_images_by_user(api, username, num_tweets, output_folder):
    status = tweepy.Cursor(api.user_timeline, screen_name=username).items()
    download_images(status, num_tweets, output_folder)
    
def download_images_by_tag(api, tag,num_tweets,   output_folder):
    status = tweepy.Cursor(api.search,  tag).items()
    download_images(status, num_tweets, output_folder)

def main():
    output_folder = 'OUTPUT5'
    consumerKey = 'yyyyy'
    consumerSecret = 'yyyyyy'
    authenticate = tweepy.OAuthHandler(consumerKey, consumerSecret)
    api = tweepy.API(authenticate, wait_on_rate_limit= True)

    # If you want to scrap images from user profile on twitter write user name and run
    # download_images_by_user(api, 'WasaySardar', 5, output_folder)
    # If you want to scrap images related to some topic from twitter write key words and run, and how many images you want
    download_images_by_tag(api, 'love...',5,  output_folder)


if __name__ == '__main__':
    main()
