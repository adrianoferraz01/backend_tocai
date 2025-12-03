import os
import json
from flask import Flask, redirect, url_for, session, request, render_template, flash
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from database import (
    register_user,
    login_user,
    verify_token,
    get_or_create_user,
    update_user_with_spotify,
    get_user_by_auth_id,
    save_selected_playlist,
    get_last_selected_playlist,
    save_to_queue_history
)

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
    """Página inicial."""
    if session.get('auth_id'):
        # Usuário já está autenticado, redireciona para seleção de playlist
        return redirect(url_for('select_playlist'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página e lógica de registro."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        # Validações básicas
        if not email or not password:
            flash('Email e senha são obrigatórios.', 'danger')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('As senhas não correspondem.', 'danger')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('A senha deve ter no mínimo 6 caracteres.', 'danger')
            return redirect(url_for('register'))

        # Registrar no Supabase Auth
        user = register_user(email, password)
        if user:
            auth_id = str(user.id)
            
            # Criar usuário no banco de dados
            db_user = get_or_create_user(
                auth_id=auth_id,
                email=email,
                display_name=email.split('@')[0]  # Usa a parte antes do @ como nome inicial
            )
            
            if db_user:
                session['auth_id'] = auth_id
                session['email'] = email
                session['user_id'] = str(db_user['id'])  # IMPORTANTE: Adiciona user_id aqui
                session['user_name'] = db_user['display_name']
                flash('Registro realizado com sucesso! Agora autorize o Spotify.', 'success')
                return redirect(url_for('login_spotify'))
            else:
                flash('Erro ao criar perfil do usuário.', 'danger')
                return redirect(url_for('register'))
        else:
            flash('Erro ao registrar. Este email pode já estar cadastrado.', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página e lógica de login."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email e senha são obrigatórios.', 'danger')
            return redirect(url_for('login'))

        # Login no Supabase Auth
        auth_response = login_user(email, password)
        if auth_response:
            auth_id = str(auth_response.user.id)
            session['auth_id'] = auth_id
            session['email'] = email
            
            # Buscar usuário no banco de dados
            user = get_user_by_auth_id(auth_id)
            if user:
                session['user_id'] = str(user['id'])  # IMPORTANTE: Adiciona user_id aqui
                session['user_name'] = user['display_name']
                flash('Login realizado com sucesso!', 'success')
                
                # Se o usuário já autorizou Spotify antes, vai para jukebox
                if user.get('spotify_id'):
                    return redirect(url_for('select_playlist'))
                else:
                    # Senão, pede para autorizar Spotify
                    return redirect(url_for('login_spotify'))
            else:
                flash('Erro ao buscar perfil do usuário.', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Email ou senha incorretos.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/login_spotify')
def login_spotify():
    """Redireciona para o login do Spotify."""
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """
    Recebe o código de autorização do Spotify e atualiza o perfil do usuário
    com dados do Spotify.
    """
    sp_oauth = get_spotify_oauth()
    code = request.args.get('code')

    if not code:
        flash('Ocorreu um erro na autorização do Spotify.', 'danger')
        return redirect(url_for('login_spotify'))

    if not session.get('auth_id'):
        flash('Por favor, faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    try:
        token_info = sp_oauth.get_access_token(code)
        session['token_info'] = token_info
        
        # Obter informações do usuário Spotify
        sp = spotipy.Spotify(auth=token_info['access_token'])
        current_user = sp.current_user()
        
        # Atualizar usuário no Supabase com dados do Spotify
        auth_id = session.get('auth_id')
        result = update_user_with_spotify(
            auth_id=auth_id,
            spotify_id=current_user['id'],
            display_name=current_user['display_name'] or current_user['email'],
            email=current_user['email'],
            profile_image_url=current_user['images'][0]['url'] if current_user['images'] else None
        )
        
        if result['success']:
            updated_user = result['user']
            session['user_id'] = str(updated_user['id'])
            session['user_name'] = updated_user['display_name']
            flash('Perfil atualizado com dados do Spotify!', 'success')
            return redirect(url_for('select_playlist'))
        else:
            # Erro: Spotify ID já está vinculado a outro usuário
            error_msg = result['error']
            if 'já está vinculada' in error_msg:
                flash(f"❌ Esta conta Spotify já está vinculada a outro usuário ({result.get('existing_user_email', 'desconhecido')}).\n\nPor favor, use uma conta Spotify diferente ou faça login com a outra conta.", 'danger')
            else:
                flash(f'❌ Erro ao atualizar perfil: {error_msg}', 'danger')
            return redirect(url_for('login_spotify'))
            
    except Exception as e:
        print(f'Erro no callback: {e}')
        flash('Ocorreu um erro durante a autorização do Spotify.', 'danger')
        return redirect(url_for('login_spotify'))

@app.route('/select_playlist')
def select_playlist():
    """Página para selecionar a playlist desejada."""
    if not session.get('auth_id'):
        flash('Por favor, faça login primeiro.', 'warning')
        return redirect(url_for('login'))
    
    sp = get_spotipy_client()
    if not sp:
        flash('Por favor, autorize o Spotify primeiro.', 'warning')
        return redirect(url_for('login_spotify'))
    
    return render_template('select_playlist.html')

@app.route('/jukebox')
def jukebox():
    """Página principal da jukebox."""
    if not session.get('auth_id'):
        flash('Por favor, faça login primeiro.', 'warning')
        return redirect(url_for('login'))
    
    sp = get_spotipy_client()
    if not sp:
        flash('Por favor, autorize o Spotify primeiro.', 'warning')
        return redirect(url_for('login_spotify'))
    
    playlist_id = session.get('selected_playlist_id')
    if not playlist_id:
        flash('Por favor, selecione uma playlist primeiro.', 'warning')
        return redirect(url_for('select_playlist'))
    
    return render_template('jukebox.html')

@app.route('/api/user_playlists')
def get_user_playlists():
    """Endpoint API para obter as playlists do usuário."""
    if not session.get('auth_id'):
        return {'error': 'Não autenticado.'}, 401

    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Autorização do Spotify necessária.'}, 401

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
            return {'error': 'Token de acesso expirado. Por favor, autorize novamente.'}, 401
        print(f'Erro ao obter playlists: {e}')
        return {'error': f'Erro ao carregar as playlists: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/api/set_playlist', methods=['POST'])
def set_playlist():
    """Endpoint API para definir a playlist selecionada e salvar no Supabase."""
    if not session.get('auth_id'):
        return {'error': 'Não autenticado.'}, 401

    data = request.get_json()
    playlist_id = data.get('playlist_id')

    if not playlist_id:
        return {'error': 'ID da playlist não fornecido.'}, 400

    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Autorização do Spotify necessária.'}, 401

    user_id = session.get('user_id')
    if not user_id:
        return {'error': 'Usuário não identificado.'}, 401

    try:
        playlist = sp.playlist(playlist_id)
        
        db_playlist = save_selected_playlist(
            user_id=user_id,
            spotify_playlist_id=playlist_id,
            playlist_name=playlist['name'],
            playlist_image_url=playlist['images'][0]['url'] if playlist['images'] else None
        )
        
        if db_playlist:
            session['selected_playlist_id'] = playlist_id
            session['selected_playlist_name'] = playlist['name']
            return {'message': f'Playlist "{playlist["name"]}" selecionada com sucesso!'}, 200
        else:
            return {'error': 'Erro ao salvar a playlist no banco de dados.'}, 500
            
    except spotipy.SpotifyException as e:
        print(f'Erro ao definir playlist: {e}')
        return {'error': f'Erro ao selecionar playlist: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/api/playlist_tracks')
def get_playlist_tracks():
    """Endpoint API para obter as músicas da playlist selecionada."""
    if not session.get('auth_id'):
        return {'error': 'Não autenticado.'}, 401

    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Autorização do Spotify necessária.'}, 401

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
                    'id': track['id'],
                    'name': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'uri': track['uri'],
                    'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None
                })
        
        return {'tracks': formatted_tracks}, 200

    except spotipy.SpotifyException as e:
        if 'The access token expired' in str(e):
            session.pop('token_info', None)
            return {'error': 'Token de acesso expirado. Por favor, autorize novamente.'}, 401
        print(f'Erro ao obter playlist: {e}')
        return {'error': f'Erro ao carregar a playlist: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/api/add_to_queue', methods=['POST'])
def add_to_queue():
    """Endpoint API para adicionar uma música à fila e salvar no histórico."""
    if not session.get('auth_id'):
        return {'error': 'Não autenticado.'}, 401

    sp = get_spotipy_client()
    if not sp:
        return {'error': 'Autorização do Spotify necessária.'}, 401

    data = request.get_json()
    track_uri = data.get('track_uri')
    track_name = data.get('track_name')
    track_artist = data.get('track_artist')
    track_id = data.get('track_id')

    if not track_uri:
        return {'error': 'URI da faixa não fornecida.'}, 400

    user_id = session.get('user_id')

    try:
        sp.add_to_queue(track_uri)
        
        if user_id and track_id:
            save_to_queue_history(
                user_id=user_id,
                spotify_track_id=track_id,
                track_name=track_name or 'Unknown',
                track_artist=track_artist or 'Unknown',
                playlist_id=None
            )
        
        return {'message': 'Música adicionada à fila com sucesso!'}, 200
    except spotipy.SpotifyException as e:
        if 'No active device found' in str(e):
            return {'error': 'Nenhum dispositivo ativo encontrado. Por favor, inicie a reprodução no Spotify.'}, 409
        elif 'The access token expired' in str(e):
            session.pop('token_info', None)
            return {'error': 'Token de acesso expirado. Por favor, autorize novamente.'}, 401
        print(f'Erro ao adicionar à fila: {e}')
        return {'error': f'Erro ao adicionar à fila: {e}'}, 500
    except Exception as e:
        print(f'Erro inesperado: {e}')
        return {'error': f'Ocorreu um erro inesperado: {e}'}, 500

@app.route('/logout')
def logout():
    """Remove o token de sessão e desloga o usuário."""
    try:
        session.pop('auth_id', None)
        session.pop('email', None)
        session.pop('user_id', None)
        session.pop('user_name', None)
        session.pop('token_info', None)
        session.pop('selected_playlist_id', None)
        session.pop('selected_playlist_name', None)
        session.modified = True
        
        flash('Você foi desconectado.', 'info')
        return redirect(url_for('index'))
    except Exception as e:
        print(f'Erro ao fazer logout: {e}')
        flash('Ocorreu um erro ao desconectar. Tente novamente.', 'danger')
        return redirect(url_for('index'))

@app.before_request
def log_session():
    """Log da sessão para debug."""
    print(f"📍 Rota: {request.path}")
    print(f"📦 Session data: auth_id={session.get('auth_id')}, user_id={session.get('user_id')}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)