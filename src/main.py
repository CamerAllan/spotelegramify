#!/usr/bin/env python
"""
Bot to build playlists.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.
"""

import logging
import os
import re
import sqlite3
import sys
import urllib.parse
from typing import List

from telegram import Update
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater
from music_services.music_service import MusicService, get_all_music_services, get_music_service_by_id
from music_services.things import Playlist, Track

# Import these so that subclasses call works
from music_services.spotify import SpotifyMusicService
from music_services.things import Playlist, Track
from music_services.tidal import TidalMusicService

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from environment
SPOTELEGRAMIFY_TELEGRAM_TOKEN = (
    os.getenv("SPOTELEGRAMIFY_KEY") if sys.argv[1] != "test" else os.getenv("SPOTELEGRAMIFY_TEST_KEY")
)
SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID = os.getenv("SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID")

available_services: List[MusicService] = []


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


def set_chat_playlist_guard(update: Update, context):

    chat_id = update.message.chat.id
    user_name = update.message.from_user["username"]
    user_id = update.message.from_user["id"]
    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

    # Only admin user can update playlist ID
    if str(user_id) != str(SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID):
        logger.warning(f"User with id {user_id} doesn't match admin user {SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID} !")
        update.message.reply_text("Only the admin user can change the playlist ID!")
        return

    if len(context.args) < 2:
        logger.info(f"Invalid use of set_playlist.")
        update.message.reply_text(f"Invalid use of set_playlist!")
        return

    music_service_id = context.args[0]
    playlist_id = context.args[1]

    service = get_music_service_by_id(available_services, music_service_id)

    if service is None:
        all_service_ids = [s.id for s in available_services]
        update.message.reply_text(f"Unknown music service '{music_service_id}'")
        update.message.reply_text(f"Try one of these: '{all_service_ids}'")
        return None

    service_playlist = service.lookup_service_playlist(playlist_id)
    if service_playlist is None:
        logger.info(f"Playlist ID '{playlist_id}' is not valid for {service.name}.")
        update.message.reply_text(f"Playlist ID '{playlist_id}' is not valid for {service.name}!")
        return

    playlist = service.convert_playlist(service_playlist)

    set_chat_playlist(service, playlist, chat_id)

    update.message.reply_text(
        f"Songs in this chat will be added to {service.name} playlist '{playlist.name}'.\nLink to playlist:\n{playlist.link}"
    )


def set_chat_playlist(service: MusicService, playlist: Playlist, chat_id) -> bool:
    """
    To function, the bot needs a playlist to add tracks to.
    If playlist has not been set, the bot should respond with instructions on how to do so.

    To set the playlist, users use the set_playlist command, which calls this function.
    This function takes the playlist ID provided by the user and stores it locally,
    so that future messages in the chat can be associated with the playlist.
    """

    logging.info(f"Setting {service.name} playlist to {playlist.name}")

    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        UPDATE chats 
        SET {service.id}_playlist_id = ?
        WHERE chat_id = ?
        """,
        (playlist.id, chat_id),
    )
    conn.commit()
    conn.close()


def get_chat_playlist_id(service: MusicService, chat_id):
    """
    Get the stored playlist associated with the given chat.
    """
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT {service.id}_playlist_id FROM chats WHERE chat_id = ?
        """,
        (chat_id,),
    )

    result = cursor.fetchone()
    conn.commit()
    conn.close()

    return result[0] if result is not None else None


def parse_track_links(update: Update, _):
    """
    This is the main event handler for this bot.
    It will read all messages in the chat, looking for music links.
    It will then add these links to a previously configured playlist.
    """

    text = update.message.text
    chat_id = str(update.message.chat.id)
    user_name = update.message.from_user["username"]
    chat_name = update.message.chat.title if update.message.chat.title is not None else user_name

    tracks: List[Track] = []
    for service in available_services:
        track_ids = service.find_track_ids(text)
        album_ids = service.find_album_ids(text)
        service_tracks = []

        # Scrape track ids and add these tracks
        if len(track_ids) > 0:
            service_tracks += [service.lookup_service_track(track_id) for track_id in track_ids]

        # Scrape album ids and add a single track from these albums
        if len(album_ids) > 0:
            service_albums = [service.lookup_service_album(album_id) for album_id in album_ids]
            service_tracks += [service.get_service_track_from_album(service_album) for service_album in service_albums]

        # Fitler out any None entries due to error
        service_tracks = [st for st in service_tracks if st]

        tracks += service.convert_tracks(service_tracks)

    if len(tracks) < 1:
        logger.debug("No tracks in message")
        return

    for service in available_services:
        playlist_id = get_chat_playlist_id(service, chat_id)
        if playlist_id is None:
            logging.info(f"{service.name} playlist not configured for chat {chat_name}")
            continue
        service_playlist = service.lookup_service_playlist(playlist_id)

        for track in tracks:
            service_track = service.search_track(track)
            if service_track is None:
                logger.info(f"{service.name} returned no results for track '{track.name} - {track.artist_name}'")
                continue
            service.add_to_playlist(service_playlist, service_track)

    logger.info(f"Processed {len(tracks)} track")


def error(update, context):
    """
    Log Errors caused by Updates.
    """
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# TODO test this
def initialise(update, context):
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

    for service in get_all_music_services():
        available_service = None

        try:
            available_service = service()
        except Exception as e:
            logger.warning(e)

        if available_service is None:
            logger.warning(f"Unable to initialise service {service.__name__}")
        else:
            available_services.append(available_service)

    if len(available_services) < 1:
        logger.error(f"Unable to initialise any music services, shutting down")
        logger.error(f"Fix environment settings and retry")
        raise exit(1)

    updater = Updater(token=SPOTELEGRAMIFY_TELEGRAM_TOKEN, use_context=True)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("init", initialise))
    dp.add_handler(CommandHandler("set_playlist", set_chat_playlist_guard))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.all, parse_track_links))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
