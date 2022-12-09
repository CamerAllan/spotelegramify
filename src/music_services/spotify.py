import logging
import os
from typing import Dict, List
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

import urllib.parse
from music_services.music_service import MusicService
from music_services.things import Playlist, Track

logger = logging.getLogger(__name__)

SPOTELEGRAMIFY_CLIENT_ID = os.getenv("SPOTELEGRAMIFY_CLIENT_ID")
SPOTELEGRAMIFY_CLIENT_SECRET = os.getenv("SPOTELEGRAMIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")


class SpotifyMusicService(MusicService):
    def __init__(self):
        self.name = "Spotify"
        self.id = "spotify"
        self.regex = r"spotify\.com/track/([a-zA-Z0-9]{22})"
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
        logger.info(f"Found playlist '{playlist_name}' on {self.name}")
        return playlist

    def lookup_service_track(self, track_id) -> Dict:
        logging.info(f"Searching for track with ID '{track_id}' on {self.name}")
        try:
            track = self.session.track(track_id)
            track_name = track["name"]
            logging.info(f"Found track '{track_name}' on {self.name}")
            return track
        except Exception as e:
            logging.info(e)
            logging.info(f"No track with ID {track_id} on {self.name}")
            return None

    def search_track(self, track: Track):
        query = urllib.parse.quote(f"track:{track.name} artist:{track.artist_name}".encode("utf8"))
        results = self.session.search(query, type="track")
        track_results = results["tracks"]

        # Validate results
        if track_results is None:
            logger.warning(f"Could not find track {track.name} - {track.artist_name} on {self.name}")
            return None

        if track_results["total"] < 1:
            logger.error(f"{self.name} returned empty tracks result for {track.name} - {track.artist_name}!")
            return None

        return track_results["items"][0]

    def playlist_contains_track(self, playlist_id: str, service_track: Dict):
        track_id = service_track["id"]
        playlist_items = self.session.playlist_items(playlist_id)["items"]

        return len([t for t in playlist_items if t["track"]["id"] == track_id]) > 0

    def add_to_playlist(self, playlist: Dict, service_track: Dict):
        track_name = service_track["name"]
        playlist_name = playlist["name"]
        track_id = service_track["id"]
        self.refresh_auth()
        if self.playlist_contains_track(playlist["id"], service_track):
            logger.info(f"Track '{track_name}' is already in {self.name} playlist '{playlist_name}'")
            return
        logger.info(f"Adding track '{track_name}' to {self.name} playlist '{playlist_name}'")
        self.session.playlist_add_items(playlist["id"], [track_id])

    def convert_tracks(self, tracks: List[Dict]) -> List[Track]:
        logging.info(f"Converting {len(tracks)} tracks from {self.name}")
        return [Track(track["name"], track["artists"][0]["name"]) for track in tracks]

    def convert_playlist(self, playlist: List[any]) -> List[Playlist]:
        playlist_name = playlist["name"]
        logging.info(f"Converting playlist {playlist_name} from {self.name}")
        service_tracks = [t["track"] for t in self.session.playlist_items(playlist["id"])["items"]]
        tracks = self.convert_tracks(service_tracks)
        return Playlist(playlist_name, tracks, playlist["external_urls"]["spotify"], playlist["id"])
