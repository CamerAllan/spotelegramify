#!/usr/bin/env python
"""
Bot to build playlists.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.
"""

# https://dev.to/sabareh/how-to-get-the-spotify-refresh-token-176
# bless u

import logging
import os
import sqlite3
import re
from telegram import Update
from telegram.ext import Filters, MessageHandler, CommandHandler, ContextTypes, Updater
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

SPOTELEGRAMIFY_CLIENT_ID = os.getenv("SPOTELEGRAMIFY_CLIENT_ID")
SPOTELEGRAMIFY_CLIENT_SECRET = os.getenv("SPOTELEGRAMIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTELEGRAMIFY_TELEGRAM_TOKEN = os.getenv("SPOTELEGRAMIFY_KEY")

# TODO refresh credentials now and then
client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTELEGRAMIFY_CLIENT_ID, client_secret=SPOTELEGRAMIFY_CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
spotify_oauth = SpotifyOAuth(client_id=SPOTELEGRAMIFY_CLIENT_ID,
                             client_secret=SPOTELEGRAMIFY_CLIENT_SECRET,
                             scope="playlist-modify-private,playlist-modify-public",
                             redirect_uri="https://localhost:8888")

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def configure_db():

    # Connect to the database
    conn = sqlite3.connect("spotelegramify")

    # Create a cursor object
    cursor = conn.cursor()

    # Create the `chats` table if it does not already exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            chat_name TEXT,
            playlist_id TEXT
        )
    """)

    # Save the changes
    conn.commit()


configure_db()


def set_playlist(update: Update, context):
    """Send a message when the command /start is issued."""
    chat_id = update.message.chat.id
    user_name = update.message.from_user["username"]

    if user_name != "CamerAllan":
        update.message.reply_text('Nope!')
        return

    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

    playlist_id = context.args[0]
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO chats (chat_id, chat_name, playlist_id)
        VALUES (?, ?, ?)
    """, (chat_id, chat_name, playlist_id))
    conn.commit()
    conn.close()


def get_playlist(chat_id):
    """Send a message when the command /start is issued."""
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT playlist_id FROM chats WHERE chat_id = '{chat_id}'
    """)

    result = cursor.fetchone()
    conn.commit()
    conn.close()

    # TODO test playlist id not set

    return result[0] if result is not None else None


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def find_spotify_track_ids(message):
    return re.findall(r'https?://.*\.spotify\.com/track/([^\s]+)\?', message)


def search_track(track):
    return sp.track(track)


def handle_messages(update: Update, ctx):
    text = (update.message.text)
    print(text)

    # TODO: Get tidal tracks
    spotify_tracks = find_spotify_track_ids(text)

    for track_id in spotify_tracks:
        track_result = search_track(track_id)
        if track_result is None:
            raise RuntimeError("No result for track with id: {track_id}")

        track_name = track_result["name"]

        # TODO: get all artists on track, not just first
        track_artist = track_result["artists"][0]["name"]
        logging.info(f"Identified track: {track_name} - {track_artist}")

        chat_playlist_id = get_playlist(update.message.chat.id)
        print(chat_playlist_id)
        if chat_playlist_id is None:
            # TODO Send message asking users to set playlist
            logger.warning("No playlist id set, cannot add to playlist")

        print(f"track: {track_id}")
        print(f"playlist: {chat_playlist_id}")
        spotify_oauth.refresh_access_token(
            refresh_token=SPOTIFY_REFRESH_TOKEN)["access_token"]
        sp.playlist_add_items(chat_playlist_id, [track_id])
        logger.info(f"Added {track_name} to playlist {chat_playlist_id}")


def main():
    """Start the bot."""

    # Configure the database
    configure_db()

    # Create the Updater and pass it your bot's token.
    updater = Updater(token=SPOTELEGRAMIFY_TELEGRAM_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("set_playlist", set_playlist))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.all, handle_messages))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
