#!/usr/bin/env python
"""
Bot to build playlists.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.
"""

import logging
import os
import sqlite3
import re
import spotipy
import tidalapi
import urllib.parse

from telegram import Update
from telegram.ext import Filters, MessageHandler, CommandHandler, Updater
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
TIDAL_ACCESS_TOKEN = os.getenv("TIDAL_ACCESS_TOKEN")
TIDAL_REFRESH_TOKEN = os.getenv("TIDAL_REFRESH_TOKEN")

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

# Set up tidal auth
tidal_session = tidalapi.Session()
# Access token can be stale but needs to have been valid
tidal_session.load_oauth_session("Bearer", TIDAL_ACCESS_TOKEN, TIDAL_REFRESH_TOKEN)


def refresh_spotify_access_token():
    """
    Spotify oAuth2 access tokens only live for 1 hour.
    We *should* cache the token and refresh only once expired.
    Let's not bother.
    """
    spotify_oauth.refresh_access_token(refresh_token=SPOTIFY_REFRESH_TOKEN)["access_token"]
    logger.info(f"Refreshed access token")


def configure_db():
    """
    Set up a local database to track the playlist associated with each Telegram chat.
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


def validate_playlist_id(playlist_id):
    """
    Return true if the given playlist ID is valid, else false
    """
    return sp.playlist(playlist_id) is not None


def set_chat_playlist(update: Update, context):
    """
    To function, the bot needs a playlist to add tracks to.
    If playlist has not been set, the bot should respond with instructions on how to do so.

    To set the playlist, users use the set_playlist command, which calls this function.
    This function takes the playlist ID provided by the user and stores it locally,
    so that future messages in the chat can be associated with the playlist.
    """
    chat_id = update.message.chat.id
    user_name = update.message.from_user["username"]
    user_id = update.message.from_user["id"]

    # Only admin user can update playlist ID
    if str(user_id) != str(SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID):
        logger.warning(f"User with id {user_id} doesn't match admin user {SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID} !")
        update.message.reply_text("Only the admin user can change the playlist ID!")
        return

    if len(context.args) < 1:
        logger.info(f"Invalid use of set_playlist.")
        update.message.reply_text(f"Missing playlist ID!")
        return

    playlist_id = context.args[0]

    # Validate the playlist ID
    playlist = None
    try:
        playlist = sp.playlist(playlist_id)
    except Exception:
        logger.info(f"Playlist ID '{playlist_id}' is not valid.")
        update.message.reply_text(f"Playlist ID '{playlist_id}' is not valid!")
        return

    playlist_name = playlist["name"]
    playlist_link = playlist["external_urls"]["spotify"]

    update.message.reply_text(
        f"Songs in this chat will be added to '{playlist_name}'.\nLink to playlist: {playlist_link}"
    )

    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

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


def get_playlist_id(chat_id):
    """
    Get the stored playlist associated with the given chat.
    """
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT playlist_id FROM chats WHERE chat_id = ?
    """,
        (chat_id,),
    )

    result = cursor.fetchone()
    conn.commit()
    conn.close()

    return result[0] if result is not None else None


def error(update, context):
    """
    Log Errors caused by Updates.
    """
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def find_spotify_track_ids(message):
    """
    Parse the message for spotify track IDs.
    This is brittle, and will break one day.
    That's ok.
    """
    # Track id is alphanumeric 22 chars long
    return re.findall(r"spotify\.com/track/([a-zA-Z0-9]{22})", message)


def find_tidal_track_ids(message):
    """
    Parse the message for tidal track IDs.
    This is brittle, and will probably break one day.
    That's ok.
    """
    # Track id is alphanumeric 22 chars long
    return re.findall(r"tidal\.com/track/(\d+)/?[^\?]*", message)


def spotify_track_id_lookup(track_id):
    """
    Use the track ID to fetch and return the track object.
    """
    return sp.track(track_id)


def tidal_track_id_lookup(track_id):
    """
    Use the track ID to fetch and return the Tidal track object.
    Then do a Spotify search for the track, and return the result.
    """

    tidal_track = tidal_session.track(track_id)

    tidal_track_artist = tidal_track.artist.name
    tidal_track_name = tidal_track.name

    logger.info(f"Looking up tidal track {tidal_track_name} - {tidal_track_artist} on Spotify")

    # Perform the search
    query = urllib.parse.quote(f"track:{tidal_track_name} artist:{tidal_track_artist}".encode("utf8"))
    spotify_results = sp.search(query, type="track")
    spotify_track_results = spotify_results["tracks"]

    # Validate results
    if spotify_track_results is None:
        logger.warning(f"Could not find tidal track {tidal_track_name} - {tidal_track_artist} on Spotify")
        return None

    if spotify_track_results["total"] < 1:
        logger.error(f"Spotify returned empty tracks result for {tidal_track_name} - {tidal_track_artist}!")
        return None

    # Return the top search result
    spotify_track_result = spotify_track_results["items"][0]
    spotify_track_artist = spotify_track_result["artists"][0]["name"]
    spotify_track_name = spotify_track_result["name"]
    logger.info(
        f"Successful lookup! Tidal: {tidal_track_name} - {tidal_track_artist} "
        f"matched Spotify: {spotify_track_name} - {spotify_track_artist}"
    )

    return spotify_track_result


def parse_track_links(update: Update, _):
    """
    This is the main event handler for this bot.
    It will read all messages in the chat, looking for music links.
    It will then add these links to a previously configured playlist.
    """

    text = update.message.text

    spotify_track_ids = find_spotify_track_ids(text)
    tidal_track_ids = find_tidal_track_ids(text)

    # Build a list of Spotify track objects from the Spotify and Tidal track IDs
    all_spotify_tracks = [spotify_track_id_lookup(track) for track in spotify_track_ids] + [
        tidal_track_id_lookup(track) for track in tidal_track_ids
    ]

    for track in all_spotify_tracks:
        if track is None:
            continue

        track_name = track["name"]

        track_artist = track["artists"][0]["name"]
        logging.info(f"Identified track: {track_name} - {track_artist}")

        chat_playlist_id = get_playlist_id(update.message.chat.id)
        if chat_playlist_id is None:
            logger.warning("No playlist id set, cannot add to playlist")
            update.message.reply_text("No playlist configured!")
            update.message.reply_text("Please set playlist id by sending `set_playlist <id>`")
            update.message.reply_text("You can find the playlist id by sharing a link to your playlist.")
            update.message.reply_text("In the following (broken) example, the playlist ID is 28XIcmCYkCabWX3f172AbW:")
            update.message.reply_text("https://open.spotify.com/playlist/28XIcmCYkCabWX3f172AbW?si=2b1d1d361s284f56")
            return

        add_track_to_playlist(chat_playlist_id, track_name, track)


def add_track_to_playlist(chat_playlist_id, track_name, track):
    """
    Add a given track to the given playlist.
    """
    logger.info(f"Attempting to add {track_name} to playlist {chat_playlist_id}")

    track_id = track["id"]
    refresh_spotify_access_token()

    # Back out if track is already in playlist
    existing_tracks = sp.playlist_items(chat_playlist_id)["items"]
    if len([t for t in existing_tracks if t["track"]["id"] == track_id]) > 0:
        logger.warning(f"Playlist {chat_playlist_id} already contains track {track_name}")
        return

    sp.playlist_add_items(chat_playlist_id, [track_id])

    logger.info(f"Successfully added {track_name} to playlist {chat_playlist_id}")


def main():
    """
    Start the bot.
    """
    # Configure the database
    configure_db()

    # Set up the bot
    updater = Updater(token=SPOTELEGRAMIFY_TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Set up handlers
    dp.add_handler(CommandHandler("set_playlist", set_chat_playlist))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.all, parse_track_links))
    dp.add_error_handler(error)

    # Start the dang thing
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
