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
from typing import List
import urllib.parse
import sys

from telegram import Update
from telegram.ext import Filters, MessageHandler, CommandHandler, Updater
from music_services.music_service import MusicService, Playlist, get_available_music_services

from music_services.spotify import SpotifyMusicService
from music_services.tidal import TidalMusicService

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from environment
# TODO Sort this bollocks out
SPOTELEGRAMIFY_TELEGRAM_TOKEN = (
    os.getenv("SPOTELEGRAMIFY_KEY") if sys.argv[1] != "test" else os.getenv("SPOTELEGRAMIFY_TEST_KEY")
)
SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID = os.getenv("SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID")

MUSIC_SERVICES: List(MusicService) = get_available_music_services()


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

    service_name = context.args[0]
    playlist_id = context.args[1]

    matching_services = [s for s in MUSIC_SERVICES if s.name.lower() == service_name]
    if len(matching_services < 1):
        logger.info(f"Invalid service {service_name}.")
        update.message.reply_text(f"Unknown service '{service_name}'!")
        return

    service = matching_services[0]

    service.lookup_playlist()
    service_playlist = service.lookup_playlist(playlist_id)
    if service_playlist is None:
        logger.info(f"Playlist ID '{playlist_id}' is not valid for {service.name}.")
        update.message.reply_text(f"Playlist ID '{playlist_id}' is not valid for {service.name}!")
        return

    playlist = service.convert_playlist(playlist)

    set_chat_playlist(service, playlist_id)

    update.message.reply_text(
        f"Songs in this chat will be added to Spotify playlist '{playlist.name}'.\nLink to playlist:\n{playlist_link}"
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
        """
        UPDATE chats 
        SET ?_playlist_id = ?
        WHERE chat_id = ?
        """,
        (service.id, playlist.id, chat_id),
    )
    conn.commit()
    conn.close()


def get_service_playlist_id(service: MusicService, chat_id):
    """
    Get the stored playlist associated with the given chat.
    """
    conn = sqlite3.connect("spotelegramify")
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT ?_playlist_id FROM chats WHERE chat_id = ?
        """,
        (
            service.id,
            chat_id,
        ),
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

    tracks = []
    for service in MUSIC_SERVICES:
        tracks += service.convert_track(service.find_track_ids(text))

    if len(tracks) < 1:
        return

    # added_to_any = False

    for service in MUSIC_SERVICES:
        playlist_id = get_service_playlist_id(service, chat_id)
        service_playlist = service.lookup_service_playlist(playlist_id)

        for track in tracks:
            service_track = service.search_track(track)
            service.add_to_playlist(service_playlist, service_track)

    # TODO
    # if not added_to_any:
    #     update.message.reply_text(f"No Spotify or Tidal playlist has been configured for this chat!")
    #     update.message.reply_text(f"You can set this up by running one of the following:")
    #     update.message.reply_text(f"/set_spotify_playlist <spotify-playlist-id>")
    #     update.message.reply_text(f"/set_tidal_playlist <tidal-playlist-id>")


def error(update, context):
    """
    Log Errors caused by Updates.
    """
    logger.warning('Update "%s" caused error "%s"', update, context.error)


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
    dp.add_handler(CommandHandler("set_playlist", set_chat_spotify_playlist))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.all, parse_track_links))
    dp.add_error_handler(error)

    # Start the dang thing
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
