<br />
<div align="center">
  <a href="https://github.com/camerallan/spotelegramify">
    <img src="./docs/images/icon.png" alt="Logo" width="80" height="80">
  </a>

  <h1 align="center">Spotelegramify</h1>

</div>

A telegram bot that grabs music links from chats and adds them to a playlist


## Limitations

It's difficult to have the user auth with a Telegram bot, which would be the preferred way to run an app like this.

Instead, the app runs 'single tenant', so an instance must be running for each admin user.
Only playlists owned by the admin user can be accessed by a given instance of this bot.
This limitation in part stems from the fact that only the owner of a playlist may add tracks through the API, even on collaborative playlists. 

## Instructions

### Installation

#### From source

```bash
git clone git@github.com:CamerAllan/spotelegramify.git
cd spotelegramify
pip install -r requirements.txt
```

### Environment

The following environmental variables must be set:

| Variable | Purpose |
| ---------|---------|
| `SPOTELEGRAMIFY_CLIENT_ID` | Spotify developer application client ID associated with your app |
| `SPOTELEGRAMIFY_CLIENT_SECRET` | Spotify developer application client secret associated with your app |
| `SPOTIFY_REFRESH_TOKEN` | Spotify refresh token for the admin user, see [here](https://dev.to/sabareh/how-to-get-the-spotify-refresh-token-176) for a guide |
| `SPOTELEGRAMIFY_TELEGRAM_TOKEN` | Token for the Telegram bot running this application |
| `SPOTELEGRAMIFY_ADMIN_USER_TELEGRAM_ID` | Telegram user ID of the admin user - determines who can set playlist ID in chat |

### Running

You can run this server in the background using as follows:

```bash
chmod +x ./run-server.sh
./run-server.sh
```