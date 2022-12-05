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
import sys

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
# TODO Sort this bollocks out
SPOTELEGRAMIFY_TELEGRAM_TOKEN = (
    os.getenv("SPOTELEGRAMIFY_KEY") if sys.argv[1] != "test" else os.getenv("SPOTELEGRAMIFY_TEST_KEY")
)

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


def refresh_tidal_access_token():
    """
    Refresh the tidal access token
    """
    tidal_session.load_oauth_session("Bearer", TIDAL_ACCESS_TOKEN, TIDAL_REFRESH_TOKEN)
    logger.info(f"Refreshed Tidal access token")


def refresh_spotify_access_token():
    """
    Refresh the spotify access token
    """
    spotify_oauth.refresh_access_token(refresh_token=SPOTIFY_REFRESH_TOKEN)["access_token"]
    logger.info(f"Refreshed Spotify access token")


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
            spotify_playlist_id TEXT,
            tidal_playlist_id TEXT
        )
    """
    )
    conn.commit()


def validate_playlist_id(playlist_id):
    """
    Return true if the given playlist ID is valid, else false
    """
    return sp.playlist(playlist_id) is not None


def set_chat_spotify_playlist(update: Update, context):
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
    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

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

    logging.info(f"Setting Spotify playlist to {playlist_name} in chat {chat_name}")
    update.message.reply_text(
        f"Songs in this chat will be added to Spotify playlist '{playlist_name}'.\nLink to playlist:\n{playlist_link}"
    )

    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE chats 
        SET spotify_playlist_id = ?
        WHERE chat_id = ?
        """,
        (playlist_id, chat_id),
    )
    conn.commit()
    conn.close()


def set_chat_tidal_playlist(update: Update, context):
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
    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

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
        # TODO verify exception
        playlist = tidalapi.playlist.Playlist(tidal_session, playlist_id)
    except Exception:
        logger.info(f"Playlist ID '{playlist_id}' is not valid.")
        update.message.reply_text(f"Playlist ID '{playlist_id}' is not valid!")
        return

    playlist_name = playlist.name
    playlist_link = f"https://tidal.com/playlist/{playlist_id}"

    logging.info(f"Setting Tidal playlist to {playlist_name} in chat {chat_name}")
    update.message.reply_text(
        f"Songs in this chat will be added to Tidal playlist '{playlist_name}'.\nLink to playlist:\n{playlist_link}"
    )

    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE chats 
        SET tidal_playlist_id = ?
        WHERE chat_id = ?
        """,
        (playlist_id, chat_id),
    )
    conn.commit()
    conn.close()


def get_spotify_playlist_id(chat_id):
    """
    Get the stored playlist associated with the given chat.
    """
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT spotify_playlist_id FROM chats WHERE chat_id = ?
        """,
        (chat_id,),
    )

    result = cursor.fetchone()
    conn.commit()
    conn.close()

    return result[0] if result is not None else None


def get_tidal_playlist_id(chat_id):
    """
    Get the stored playlist associated with the given chat.
    """
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT tidal_playlist_id FROM chats WHERE chat_id = ?
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
    return re.findall(r"tidal\.com/.*/track/(\d+)/?[^\?]*", message)


def spotify_track_id_lookup(track_id):
    """
    Use the track ID to fetch and return the Spotify track object.
    """
    return sp.track(track_id)


def tidal_track_id_lookup(track_id):
    """
    Use the track ID to fetch and return the Tidal track object.
    """

    return tidal_session.track(track_id)


def convert_tidal_track_to_spotify(tidal_track):
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


def convert_spotify_track_to_tidal(spotify_track):
    tidal_track_artist = spotify_track["artists"][0]["name"]
    tidal_track_name = spotify_track["name"]

    logger.info(f"Looking up Spotify track {tidal_track_name} - {tidal_track_artist} on Tidal")

    # Perform the search
    # query = urllib.parse.quote(f"track:{spotify_track_name} artist:{spotify_track_artist}".encode("utf8"))
    query = f"{tidal_track_name} {tidal_track_artist}"
    tidal_results = tidal_session.search(query, models=[tidalapi.Track])

    tidal_track_result = tidal_results["top_hit"]

    # Validate results
    if tidal_track_result is None:
        logger.warning(f"Could not find Spotify track {tidal_track_name} - {tidal_track_artist} on Tidal")
        return None

    # Return the top search result
    tidal_track_artist = tidal_track_result.artist.name
    tidal_track_name = tidal_track_result.name
    logger.info(
        f"Successful lookup! Tidal: {tidal_track_name} - {tidal_track_artist} "
        f"matched Spotify: {tidal_track_name} - {tidal_track_artist}"
    )

    return tidal_track_result


def parse_track_links(update: Update, _):
    """
    This is the main event handler for this bot.
    It will read all messages in the chat, looking for music links.
    It will then add these links to a previously configured playlist.
    """

    text = update.message.text

    spotify_track_ids = find_spotify_track_ids(text)
    tidal_track_ids = find_tidal_track_ids(text)

    message_spotify_tracks = [spotify_track_id_lookup(track) for track in spotify_track_ids]
    message_tidal_tracks = [tidal_track_id_lookup(track) for track in tidal_track_ids]

    all_spotify_tracks = message_spotify_tracks + [
        convert_tidal_track_to_spotify(track) for track in message_tidal_tracks
    ]
    all_tidal_tracks = message_tidal_tracks + [
        convert_spotify_track_to_tidal(track) for track in message_spotify_tracks
    ]

    if len(all_spotify_tracks) < 1 and len(all_tidal_tracks) < 1:
        return

    added_to_any = False

    for track in all_spotify_tracks:
        if track is None:
            continue

        track_name = track["name"]

        chat_tidal_playlist_id = get_spotify_playlist_id(update.message.chat.id)
        if chat_tidal_playlist_id is None:
            logger.info(f"No Spotify playlist id set, cannot add {track_name} to Spotify playlist")
            continue

        added_to_any = add_track_to_spotify_playlist(update, chat_tidal_playlist_id, track_name, track) or added_to_any

    for track in all_tidal_tracks:
        if track is None:
            continue

        track_name = track.name

        chat_tidal_playlist_id = get_tidal_playlist_id(update.message.chat.id)
        if chat_tidal_playlist_id is None:
            logger.info(f"No Tidal playlist id set, cannot add {track_name} to Tidal playlist")
            continue

        added_to_any = add_track_to_tidal_playlist(update, chat_tidal_playlist_id, track_name, track) or added_to_any

    if not added_to_any:
        update.message.reply_text(f"No Spotify or Tidal playlist has been configured for this chat!")
        update.message.reply_text(f"You can set this up by running one of the following:")
        update.message.reply_text(f"/set_spotify_playlist <spotify-playlist-id>")
        update.message.reply_text(f"/set_tidal_playlist <tidal-playlist-id>")


def add_track_to_spotify_playlist(update, chat_playlist_id, track_name, track):
    """
    Add a given track to the given Spotify playlist.
    """

    track_id = track["id"]
    refresh_spotify_access_token()

    # Back out if track is already in playlist
    spotify_playlist = sp.playlist(chat_playlist_id)
    playlist_name = spotify_playlist["name"]

    logger.info(f"Attempting to add '{track_name}' to Spotify playlist '{playlist_name}'")

    spotify_playlist_items = sp.playlist_items(chat_playlist_id)
    existing_tracks = spotify_playlist_items["items"]
    if len([t for t in existing_tracks if t["track"]["id"] == track_id]) > 0:
        logger.info(f"Spotify playlist '{playlist_name}' already contains track '{track_name}'")
        update.message.reply_text(f"That song is already in the Spotify playlist {playlist_name}!")
        return True

    sp.playlist_add_items(chat_playlist_id, [track_id])

    logger.info(f"Successfully added {track_name} to Spotify playlist '{playlist_name}'")

    return True


def add_track_to_tidal_playlist(update, chat_playlist_id, track_name, track):
    """
    Add a given track to the given Tidal playlist.
    """

    track_id = track.id
    refresh_tidal_access_token()

    tidal_playlist = tidal_session.playlist(chat_playlist_id)
    playlist_name = tidal_playlist.name

    logger.info(f"Attempting to add '{track_name}' to Tidal playlist '{playlist_name}'")

    # Back out if track is already in playlist
    existing_tracks = tidal_playlist.tracks()
    if len([t for t in existing_tracks if t.id == track_id]) > 0:
        logger.warning(f"Tidal playlist '{playlist_name}' already contains track '{track_name}'")
        update.message.reply_text(f"That song is already in the Tidal playlist {playlist_name}!")
        return True

    tidal_playlist.add([track_id])

    logger.info(f"Successfully added '{track_name}' to Tidal playlist '{playlist_name}'")

    return True


# TODO test this
def bot_added_to_chat(update, context):
    chat_id = str(update.message.chat.id)
    user_name = update.message.from_user["username"]
    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO chats (chat_id)
        VALUES (?)
        """,
        (chat_id,),
    )
    conn.commit()
    conn.close()
    logger.info(f"Initialisted DB for chat {chat_name}")


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
    dp.add_handler(CommandHandler("init", bot_added_to_chat))
    dp.add_handler(CommandHandler("set_spotify_playlist", set_chat_spotify_playlist))
    dp.add_handler(CommandHandler("set_tidal_playlist", set_chat_tidal_playlist))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.all, parse_track_links))
    dp.add_error_handler(error)

    # Start the dang thing
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
