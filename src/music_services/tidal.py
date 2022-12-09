import logging
import os
from typing import Dict, List
import tidalapi

from music_services.music_service import MusicService
from music_services.things import Track

logger = logging.getLogger(__name__)


TIDAL_ACCESS_TOKEN = os.getenv("TIDAL_ACCESS_TOKEN")
TIDAL_REFRESH_TOKEN = os.getenv("TIDAL_REFRESH_TOKEN")


class TidalMusicService(MusicService):
    @property
    def name(self):
        return "Tidal"

    @property
    def id(self):
        return "tidal"

    @property
    def regex(self):
        return r"tidal\.com/.*/track/(\d+)/?[^\?]*"

    def __init__(self):
        self.session = tidalapi.Session()
        super().__init__()

    def refresh_auth(self):
        logger.info(f"Refreshing {self.name} access token")
        self.session.load_oauth_session("Bearer", TIDAL_ACCESS_TOKEN, TIDAL_REFRESH_TOKEN)
        logger.info(f"Refreshed {self.name} access token")

    def lookup_service_playlist(self, playlist_id) -> Dict:
        logger.info(f"Looking up playlist with ID '{playlist_id}' on {self.name}")
        playlist = None
        try:
            playlist = tidalapi.playlist.Playlist(self.session, playlist_id)
        except Exception:
            logger.info(f"No {self.name} playlist exists with ID {playlist_id}")
            pass

        playlist_name = playlist.name
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

    def convert_tracks(self, tracks: List[Dict]) -> List[Track]:
        return [Track(track.name, track.artists[0].name) for track in tracks]
