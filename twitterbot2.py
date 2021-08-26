#
# twitterbot2
#
#   edoardottt
#   edoardoottavianelli.it
#   https://github.com/edoardottt/twitterbot2
#
#   This repository is under GPL-3 License.
#
#
# This file contains the main function and all
# the main functionalities of twitterbot2.
# There are defined here the functions to execute the
# right actions when the user inputs his/her choices.
#


import twitter
import secrets
import time
import globals
import logging
import banner
import input
import version
import sys
import db
import datetime
import stats
import output


def auth(token, token_secret, consumer_key, consumer_secret):
    """
    This function provides the authentication to twitter.
    token = access token
    token_secret = access secret token
    consumer_key = Api key
    consumer_secret = Api Secret key
    """
    t = twitter.Twitter(
        auth=twitter.OAuth(token, token_secret, consumer_key, consumer_secret)
    )
    return t


def get_home(t):
    # Get your "home" timeline
    return t.statuses.home_timeline()


def get_friend_home(t, name):
    # Get a particular friend's timeline
    return t.statuses.user_timeline(screen_name=name)


def tweet(t, message):
    # Update your status
    t.statuses.update(status=message)


def put_like(t, status, logger, count):
    # Favorite/like a status
    if not status["favorited"]:
        logger.info("Liked a tweet by {}".format(status["user"]["screen_name"]))
        t.favorites.create(_id=status["id"])
        count += 1
    return count


def retweet_tweet(t, status, logger, count):
    # Retweet a status
    if not status["retweeted"]:
        logger.info("Retweeted a tweet by {}".format(status["user"]["screen_name"]))
        t.statuses.retweet._id(_id=status["id"])
        count += 1
    return count


def search(t, term):
    # Search for the latest tweets about <term>
    return t.search.tweets(q=term)


def create_bot(logger):
    """
    This function returns the authenticated Bot object.
    """
    secretss = secrets.read_secrets()

    if secretss["access_token"] is None or secretss["access_token_secret"] is None:
        logger.error("You must modify properly the config.yaml file.")
        sys.exit(1)

    bot = auth(
        secretss["access_token"],
        secretss["access_token_secret"],
        secretss["api_key"],
        secretss["api_secret_key"],
    )
    return bot


def likes_rt_home(bot, logger, tweet_count, likes_count, retweet_count):
    """
    This function tries to put likes and retweet on the bot timeline.
    """
    home = get_home(bot)
    if home is not None:
        tweet_count += len(home)
    else:
        logger.warning("Rate limit exceeded")
        time.sleep(15 * 60)
    for tweet_home in home:
        if tweet_home["user"]["screen_name"] != globals.bot_user:
            likes_count = put_like(bot, tweet_home, logger, likes_count)
            retweet_count = retweet_tweet(bot, tweet_home, logger, retweet_count)
            time.sleep(2)

    return tweet_count, likes_count, retweet_count


def crawl_timeline(bot, logger):
    """
    This is the handle function of the -t or --timeline option.
    """
    tweet_count = 0
    likes_count = 0
    retweet_count = 0

    # check if there are values of today.
    conn = db.conn_db()
    username = globals.bot_user
    values = db.today_stats(conn, username)
    today = datetime.datetime.today().strftime("%Y-%m-%d")

    # if there aren't data, creates a record in the statistics table
    if values is None:
        db.create_stat(conn, (username, today, 0, 0, 0))
    # otherwise retrieves the values
    else:
        (
            username,
            today,
            tweet_count,
            likes_count,
            retweet_count,
        ) = values

    while True:

        logger.info("Tweets count: " + str(tweet_count))
        logger.info("Likes count: " + str(likes_count))
        logger.info("Retweets count: " + str(retweet_count))

        tweet_count, likes_count, retweet_count = likes_rt_home(
            bot, logger, tweet_count, likes_count, retweet_count
        )

        logger.info("Sleeping for one minute.")
        time.sleep(60)

        home = get_friend_home(bot, globals.user)
        if home is not None:
            tweet_count += len(home)
        else:
            logger.warning("Rate limit exceeded")
            time.sleep(15 * 60)
        for tweet_home in home:
            if tweet_home["user"]["screen_name"] != globals.bot_user:
                likes_count = put_like(bot, tweet_home, logger, likes_count)
                retweet_count = retweet_tweet(bot, tweet_home, logger, retweet_count)
                time.sleep(2)
        # update the values in the database
        today = datetime.datetime.today().strftime("%Y-%m-%d")
        values = db.today_stats(conn, username)
        # if there aren't data, creates a record in the statistics table
        if values is None:
            db.create_stat(conn, (username, today, 0, 0, 0))
            tweet_count = 0
            likes_count = 0
            retweet_count = 0
        # otherwise update the values
        else:
            db.update_stat(
                conn,
                (tweet_count, likes_count, retweet_count, username, today),
            )
        logger.info("Database updated.")

        # check if the bot reached the daily tweet cap
        if retweet_count + 40 > globals.daily_tweet_cap:
            logger.warning("Daily tweet cap reached.")
            logger.info("Sleeping for 6 hours.")
            time.sleep(6 * 60 * 60)
        else:
            logger.info("Sleeping for 15 minutes.")
            time.sleep(15 * 60)


def likes_rt_search(bot, logger, keyword, tweet_count, likes_count, retweet_count):
    """
    This function tries to put likes and retweet on the tweets searched by term.
    """
    ts = search(bot, keyword)
    statuses = ts["statuses"]

    if statuses is not None:
        tweet_count += len(statuses)
    else:
        logger.warning("Rate limit exceeded")
        time.sleep(15 * 60)
    for tweet_ts in statuses:
        if tweet_ts["user"]["screen_name"] != globals.bot_user:
            likes_count = put_like(bot, tweet_ts, logger, likes_count)
            retweet_count = retweet_tweet(bot, tweet_ts, logger, retweet_count)
            time.sleep(2)
    return tweet_count, likes_count, retweet_count


def crawl_keyword(bot, logger, keyword):
    """
    This is the handle function of the -k or --keyword option.
    """
    tweet_count = 0
    likes_count = 0
    retweet_count = 0

    # check if there are values of today.
    conn = db.conn_db()
    username = globals.bot_user
    values = db.today_stats(conn, username)
    today = datetime.datetime.today().strftime("%Y-%m-%d")

    # if there aren't data, creates a record in the statistics table
    if values is None:
        db.create_stat(conn, (username, today, 0, 0, 0))
    # otherwise retrieves the values
    else:
        (
            username,
            today,
            tweet_count,
            likes_count,
            retweet_count,
        ) = values

    while True:

        logger.info("Tweets count: " + str(tweet_count))
        logger.info("Likes count: " + str(likes_count))
        logger.info("Retweets count: " + str(retweet_count))

        tweet_count, likes_count, retweet_count = likes_rt_search(
            bot, logger, keyword, tweet_count, likes_count, retweet_count
        )
        logger.info("Sleeping for one minute.")
        time.sleep(60)

        home = get_friend_home(bot, globals.user)
        if home is not None:
            tweet_count += len(home)
        else:
            logger.warning("Rate limit exceeded")
            time.sleep(15 * 60)
        for tweet_home in home:
            if tweet_home["user"]["screen_name"] != globals.bot_user:
                likes_count = put_like(bot, tweet_home, logger, likes_count)
                retweet_count = retweet_tweet(bot, tweet_home, logger, retweet_count)
                time.sleep(2)
        # update the values in the database
        today = datetime.datetime.today().strftime("%Y-%m-%d")
        values = db.today_stats(conn, username)
        # if there aren't data, creates a record in the statistics table
        if values is None:
            db.create_stat(conn, (username, today, 0, 0, 0))
            tweet_count = 0
            likes_count = 0
            retweet_count = 0
        # otherwise update the values
        else:
            db.update_stat(
                conn,
                (tweet_count, likes_count, retweet_count, username, today),
            )
        logger.info("Database updated.")

        # check if the bot reached the daily tweet cap
        if retweet_count + 40 > globals.daily_tweet_cap:
            logger.warning("Daily tweet cap reached.")
            logger.info("Sleeping for 6 hours.")
            time.sleep(6 * 60 * 60)
        else:
            logger.info("Sleeping for 15 minutes.")
            time.sleep(15 * 60)
        logger.info("Sleeping for 15 minutes.")
        time.sleep(15 * 60)


def main():
    """
    Main function
    """
    logger = logging.getLogger(__name__)

    logging.basicConfig(
        encoding="utf-8",
        level=logging.INFO,
        format="%(levelname)s:%(asctime)s | %(message)s",
    )

    args = input.get_args()

    banner.print_banner()

    # -- VERSION --
    if args.version:
        version.print_version()

    # -- TIMELINE --
    if args.timeline:
        bot = create_bot(logger)
        crawl_timeline(bot, logger)

    # -- KEYWORD --
    if args.keyword:
        bot = create_bot(logger)
        crawl_keyword(bot, logger, args.keyword)

    # -- STATS --
    if args.stats:
        stats.check_stat(args.stats)

    # -- CSV OUTPUT --
    if args.output_csv:
        output.output_csv(args.output_csv)

    # -- JSON OUTPUT --
    if args.output_json:
        output.output_json(args.output_json)

    # -- HTML OUTPUT --
    if args.output_html:
        output.output_html(args.output_html)


if __name__ == "__main__":
    main()
