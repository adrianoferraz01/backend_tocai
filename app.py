import os
import json
from flask import Flask, redirect, url_for, session, request, render_template, flash
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')

CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('SPOTIPY_REDIRECT_URI')

SCOPES = 'user-read-playback-state user-modify-playback-state playlist-read-private user-library-read'

def get_spotify_oauth():
    """Retorna um objeto SpotifyOAuth configurado."""
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES
    )

def get_spotipy_client():
    """
    Obtém um objeto Spotipy para interagir com a API,
    atualizando o token se necessário.
    """
    sp_oauth = get_spotify_oauth()
    token_info = session.get('token_info', None)

    if not token_info:
        return None

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info

    return spotipy.Spotify(auth=token_info['access_token'])

@app.route('/')
def index():
    """Página inicial com opção de login."""
    return render_template('index.html')

@app.route('/login')
def login():
    """Redireciona o usuário para a página de autorização do Spotify."""
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """
    Recebe o código de autorização do Spotify, troca por tokens
    e os armazena na sessão.
    """
    sp_oauth = get_spotify_oauth()
    code = request.args.get('code')

    if code:
        token_info = sp_oauth.get_access_token(code)
        session['token_info'] = token_info
        flash('Login com Spotify realizado com sucesso!', 'success')
        return redirect(url_for('select_playlist'))
    else:
        flash('Ocorreu um erro no login com Spotify.', 'danger')
        return redirect(url_for('index'))

@app.route('/select_playlist')
def select_playlist():
    """Página para selecionar a playlist desejada."""
    sp = get_spotipy_client()
    if not sp:
        flash('Por favor, faça login com o Spotify.', 'warning')
        return redirect(url_for('index'))
    
    return render_template('select_playlist.html')

@app.route('/jukebox')
def jukebox():
    """Página principal da jukebox."""
    sp = get_spotipy_client()
    if not sp:
        flash('Por favor, faça login com o Spotify.', 'warning')
        return redirect(url_for('index'))
    
    playlist_id = session.get('selected_playlist_id')
    if not playlist_id:
        flash('Por favor, selecione uma playlist primeiro.', 'warning')
        return redirect(url_for('select_playlist'))
    
    return render_template('jukebox.html')

@app.route('/api/user_playlists')
def get_user_playlists():
    """Endpoint API para obter as playlists do usuário."""
    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Não autenticado. Por favor, faça login.'}, 401

    try:
        playlists = []
        results = sp.current_user_playlists(limit=50)
        playlists.extend(results['items'])
        
        while results['next']:
            results = sp.next(results)
            playlists.extend(results['items'])
        
        formatted_playlists = []
        for playlist in playlists:
            formatted_playlists.append({
                'id': playlist['id'],
                'name': playlist['name'],
                'image': playlist['images'][0]['url'] if playlist['images'] else None,
                'tracks_total': playlist['tracks']['total'],
                'owner': playlist['owner']['display_name']
            })
        
        return {'playlists': formatted_playlists}, 200

    except spotipy.SpotifyException as e:
        if 'The access token expired' in str(e):
            session.pop('token_info', None)
            return {'error': 'Token de acesso expirado. Por favor, faça login novamente.'}, 401
        print(f'Erro ao obter playlists: {e}')
        return {'error': f'Erro ao carregar as playlists: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/api/set_playlist', methods=['POST'])
def set_playlist():
    """Endpoint API para definir a playlist selecionada."""
    data = request.get_json()
    playlist_id = data.get('playlist_id')

    if not playlist_id:
        return {'error': 'ID da playlist não fornecido.'}, 400

    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Não autenticado.'}, 401

    try:
        # Verifica se a playlist existe e o usuário tem acesso
        playlist = sp.playlist(playlist_id)
        session['selected_playlist_id'] = playlist_id
        session['selected_playlist_name'] = playlist['name']
        return {'message': f'Playlist "{playlist["name"]}" selecionada com sucesso!'}, 200
    except spotipy.SpotifyException as e:
        print(f'Erro ao definir playlist: {e}')
        return {'error': f'Erro ao selecionar playlist: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/api/playlist_tracks')
def get_playlist_tracks():
    """Endpoint API para obter as músicas da playlist selecionada."""
    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Não autenticado. Por favor, faça login.'}, 401

    playlist_id = session.get('selected_playlist_id')
    if not playlist_id:
        return {'error': 'Nenhuma playlist selecionada.'}, 400

    try:
        tracks = []
        results = sp.playlist_items(playlist_id)
        tracks.extend(results['items'])
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        formatted_tracks = []
        for item in tracks:
            track = item['track']
            if track:
                formatted_tracks.append({
                    'name': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'uri': track['uri'],
                    'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None
                })
        
        return {'tracks': formatted_tracks}, 200

    except spotipy.SpotifyException as e:
        if 'The access token expired' in str(e):
            session.pop('token_info', None)
            return {'error': 'Token de acesso expirado. Por favor, faça login novamente.'}, 401
        print(f'Erro ao obter playlist: {e}')
        return {'error': f'Erro ao carregar a playlist: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/api/add_to_queue', methods=['POST'])
def add_to_queue():
    """Endpoint API para adicionar uma música à fila."""
    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Não autenticado. Por favor, faça login.'}, 401

    data = request.get_json()
    track_uri = data.get('track_uri')

    if not track_uri:
        return {'error': 'URI da faixa não fornecida.'}, 400

    try:
        sp.add_to_queue(track_uri)
        return {'message': 'Música adicionada à fila com sucesso!'}, 200
    except spotipy.SpotifyException as e:
        if 'No active device found' in str(e):
            return {'error': 'Nenhum dispositivo ativo encontrado. Por favor, inicie a reprodução no Spotify em algum dispositivo primeiro.'}, 409
        elif 'The access token expired' in str(e):
            session.pop('token_info', None)
            return {'error': 'Token de acesso expirado. Por favor, faça login novamente.'}, 401
        print(f'Erro ao adicionar à fila: {e}')
        return {'error': f'Erro ao adicionar à fila: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/logout')
def logout():
    """Remove o token de sessão e desloga o usuário."""
    session.pop('token_info', None)
    session.pop('selected_playlist_id', None)
    session.pop('selected_playlist_name', None)
    flash('Você foi desconectado do Spotify.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)