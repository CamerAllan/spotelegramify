import logging
import os
from typing import Dict
import tidalapi

from music_services.music_service import MusicService

logger = logging.getLogger(__name__)


TIDAL_ACCESS_TOKEN = os.getenv("TIDAL_ACCESS_TOKEN")
TIDAL_REFRESH_TOKEN = os.getenv("TIDAL_REFRESH_TOKEN")


class TidalMusicService(MusicService):
    def __init__(self):
        self.name = "Tidal"
        self.id = "tidal"
        self.regex = r"tidal\.com/(?:.*/)?track/(\d+)/?[^\?]*"
        self.session = tidalapi.Session()
        super().__init__()

    def refresh_auth(self):
        logger.info(f"Refreshing {self.name} access token")
        self.session.load_oauth_session("Bearer", TIDAL_ACCESS_TOKEN, TIDAL_REFRESH_TOKEN)
        logger.info(f"Refreshed {self.name} access token")

    def lookup_service_playlist(self, playlist_id) -> Dict:
        playlist = None
        try:
            playlist = tidalapi.playlist.Playlist(self.session, playlist_id)
        except Exception:
            logger.info(f"No {self.name} playlist exists with ID {playlist_id}")
            pass

        return playlist

    def lookup_service_track(self, track_id) -> Dict:
        return self.session.track(track_id)

    def search_track(self, track_name, artist_name):
        query = f"{track_name} {artist_name}"
        results = self.session.search(query, models=[tidalapi.Track])

        tidal_track_result = results["top_hit"]

        # Validate results
        if tidal_track_result is None:
            logger.warning(f"Could not find track {track_name} - {artist_name} on {self.name}")
            return None

        return tidal_track_result

    def playlist_contains_track(self, playlist_id: str, service_track):
        track_id = service_track.id
        playlist = self.session.playlist(playlist_id)
        tracks = playlist.tracks()
        return len([t for t in tracks if t.id == track_id]) > 0

    def add_to_playlist(self, playlist: Dict, service_track: Dict):
        playlist.add([service_track.id])
