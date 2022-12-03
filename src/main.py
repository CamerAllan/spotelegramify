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

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from environment
SPOTELEGRAMIFY_CLIENT_ID = os.getenv("SPOTELEGRAMIFY_CLIENT_ID")
SPOTELEGRAMIFY_CLIENT_SECRET = os.getenv("SPOTELEGRAMIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTELEGRAMIFY_TELEGRAM_TOKEN = os.getenv("SPOTELEGRAMIFY_KEY")
SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID = os.getenv("SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID")

# Set up Spotify auth object
client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTELEGRAMIFY_CLIENT_ID, client_secret=SPOTELEGRAMIFY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
spotify_oauth = SpotifyOAuth(
    client_id=SPOTELEGRAMIFY_CLIENT_ID,
    client_secret=SPOTELEGRAMIFY_CLIENT_SECRET,
    scope="playlist-modify-private,playlist-modify-public",
    redirect_uri="https://localhost:8888",
)


def configure_db():
    """
    Set up a local database to track the playlist associated with
    each Telegram chat.
    """
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            chat_name TEXT,
            playlist_id TEXT
        )
    """
    )
    conn.commit()


def set_playlist(update: Update, context):
    """Send a message when the command /start is issued."""
    chat_id = update.message.chat.id
    user_name = update.message.from_user["username"]
    user_id = update.message.from_user["id"]

    if str(user_id) != str(SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID):
        logger.warn(f"User with id {user_id} doesn't match admin user {SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID} !")
        update.message.reply_text("Nope!")
        return

    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

    playlist_id = context.args[0]
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO chats (chat_id, chat_name, playlist_id)
        VALUES (?, ?, ?)
    """,
        (chat_id, chat_name, playlist_id),
    )
    conn.commit()
    conn.close()


def get_playlist(chat_id):
    """Send a message when the command /start is issued."""
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT playlist_id FROM chats WHERE chat_id = '{chat_id}'
    """
    )

    result = cursor.fetchone()
    conn.commit()
    conn.close()

    # TODO test playlist id not set

    return result[0] if result is not None else None


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text("Help!")


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def find_spotify_track_ids(message):
    # Track id is alphanumeric 22 chars long
    return re.findall(r"https?://.*\.spotify\.com/track\/([a-zA-Z0-9]{22})", message)


def search_track(track):
    return sp.track(track)


def parse_track_links(update: Update, ctx):
    text = update.message.text

    # TODO: Parse tidal tracks too
    spotify_tracks = find_spotify_track_ids(text)

    for track_id in spotify_tracks:
        track_result = search_track(track_id)
        if track_result is None:
            raise RuntimeError("No result for track with id: {track_id}")

        track_name = track_result["name"]

        track_artist = track_result["artists"][0]["name"]
        logging.info(f"Identified track: {track_name} - {track_artist}")

        chat_playlist_id = get_playlist(update.message.chat.id)
        if chat_playlist_id is None:
            logger.warning("No playlist id set, cannot add to playlist")
            update.message.reply_text("No playlist configured!")
            update.message.reply_text("Please set playlist id by sending `set_playlist <id>`")
            update.message.reply_text("You can find the playlist id by sharing a link to your playlist.")
            update.message.reply_text("In the following (broken) example, the playlist ID is 28XIcmCYkCabWX3f172AbW:")
            update.message.reply_text("https://open.spotify.com/playlist/28XIcmCYkCabWX3f172AbW?si=2b1d1d361s284f56")
            return

        add_track_to_playlist(chat_playlist_id, track_name, track_id)


def refresh_spotify_access_token():
    """
    Spotify oAuth2 access tokens only live for 1 hour.
    We *should* cache the token and refresh only once expired.
    Let's not bother.
    """
    spotify_oauth.refresh_access_token(refresh_token=SPOTIFY_REFRESH_TOKEN)["access_token"]


def add_track_to_playlist(chat_playlist_id, track_name, track_id):
    logger.info(f"Attempting to add {track_name} to playlist {chat_playlist_id}")

    refresh_spotify_access_token()
    sp.playlist_add_items(chat_playlist_id, [track_id])

    logger.info(f"Successfully added {track_name} to playlist {chat_playlist_id}")


def main():
    """Start the bot."""
    # Configure the database
    configure_db()

    # Set up the bot
    updater = Updater(token=SPOTELEGRAMIFY_TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Set up handlers
    dp.add_handler(CommandHandler("set_playlist", set_playlist))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.all, parse_track_links))
    dp.add_error_handler(error)

    # Start the dang thing
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
