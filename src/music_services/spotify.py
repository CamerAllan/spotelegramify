import logging
import os
from typing import Dict, List
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

import urllib.parse
from music_services.music_service import MusicService
from music_services.things import Track

logger = logging.getLogger(__name__)

SPOTELEGRAMIFY_CLIENT_ID = os.getenv("SPOTELEGRAMIFY_CLIENT_ID")
SPOTELEGRAMIFY_CLIENT_SECRET = os.getenv("SPOTELEGRAMIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")


class SpotifyMusicService(MusicService):
    @property
    def name(self):
        return "Spotify"

    @property
    def id(self):
        return "spotify"

    @property
    def regex(self):
        return r"spotify\.com/track/([a-zA-Z0-9]{22})"

    def __init__(self):
        client_credentials_manager = SpotifyClientCredentials(
            client_id=SPOTELEGRAMIFY_CLIENT_ID, client_secret=SPOTELEGRAMIFY_CLIENT_SECRET
        )
        self.session = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        self.oauth = SpotifyOAuth(
            client_id=SPOTELEGRAMIFY_CLIENT_ID,
            client_secret=SPOTELEGRAMIFY_CLIENT_SECRET,
            scope="playlist-modify-private,playlist-modify-public",
            redirect_uri="https://localhost:8888",
        )
        super().__init__()

    def refresh_auth(self):
        logger.info(f"Refreshing {self.name} access token")
        self.oauth.refresh_access_token(refresh_token=SPOTIFY_REFRESH_TOKEN)["access_token"]
        logger.info(f"Refreshed {self.name} access token")

    def lookup_service_playlist(self, playlist_id) -> Dict:
        logger.info(f"Looking up playlist with ID '{playlist_id}' on {self.name}")
        playlist = None
        try:
            playlist = self.session.playlist(playlist_id)
        except Exception:
            logger.info(f"No {self.name} playlist exists with ID {playlist_id}")
            pass

        playlist_name = playlist["name"]
        logger.info(f"Found playlist '{playlist_name} on {self.name}")
        return playlist

    def lookup_service_track(self, track_id) -> Dict:
        logging.info(f"Searching for track with ID '{track_id}' on {self.name}")
        try:
            track = self.session.track(track_id)
            logging.info(f"Found track '{track.name}' on {self.name}")
            return track
        except Exception as e:
            logging.info(e)
            logging.info(f"No track with ID {track_id} on {self.name}")
            return None

    def search_track(self, track_name, artist_name):
        query = urllib.parse.quote(f"track:{track_name} artist:{artist_name}".encode("utf8"))
        results = self.session.search(query, type="track")
        track_results = results["tracks"]

        # Validate results
        if track_results is None:
            logger.warning(f"Could not find track {track_name} - {artist_name} on {self.name}")
            return None

        if track_results["total"] < 1:
            logger.error(f"{self.name} returned empty tracks result for {track_name} - {artist_name}!")
            return None

        # Return the top search result
        return track_results["items"][0]

    def playlist_contains_track(self, playlist_id: str, service_track: Dict):
        track_id = service_track["id"]
        playlist_items = self.session.playlist_items(playlist_id)["items"]

        return len([t for t in playlist_items if t["track"]["id"] == track_id]) > 0

    def add_to_playlist(self, playlist: Dict, service_track: Dict):
        track_id = service_track["id"]
        self.refresh_auth()
        if self.playlist_contains_track(playlist["id"], service_track):
            return
        self.session.playlist_add_items(playlist_id, [track_id])

    def convert_tracks(self, tracks: List[Dict]) -> List[Track]:
        return [Track(track["name"], track["artists"][0]["name"]) for track in tracks]
