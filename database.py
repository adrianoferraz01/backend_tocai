import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Configurar cliente Supabase com SERVICE_ROLE_KEY (para operações no servidor)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Funções de Autenticação ---

def register_user(email: str, password: str):
    """
    Registra um novo usuário no Supabase Auth.
    Retorna o usuário autenticado ou None se houver erro.
    """
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        print(f"✅ Usuário registrado: {email}")
        return response.user
    except Exception as e:
        print(f"❌ Erro ao registrar usuário: {e}")
        return None

def login_user(email: str, password: str):
    """
    Faz login de um usuário com email e senha.
    Retorna a sessão do usuário ou None se houver erro.
    """
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        print(f"✅ Usuário logado: {email}")
        return response
    except Exception as e:
        print(f"❌ Erro ao fazer login: {e}")
        return None

def verify_token(access_token: str):
    """
    Verifica se um token de acesso é válido e retorna o usuário.
    """
    try:
        response = supabase_client.auth.get_user(access_token)
        return response.user
    except Exception as e:
        print(f"❌ Token inválido: {e}")
        return None

# --- Funções de Usuário ---

def get_or_create_user(auth_id: str, email: str, display_name: str, spotify_id: str = None, profile_image_url: str = None):
    """
    Obtém ou cria um usuário no Supabase baseado no auth_id (UUID do Supabase Auth).
    Atualiza com dados do Spotify se fornecidos.
    """
    try:
        # Tenta buscar o usuário existente
        response = supabase.table('users').select('*').eq('auth_id', auth_id).execute()
        
        if response.data:
            user = response.data[0]
            print(f"✅ Usuário encontrado: {user['display_name']}")
            return user
        else:
            # Usuário não existe, cria um novo
            new_user = {
                'auth_id': auth_id,
                'email': email,
                'display_name': display_name,
                'spotify_id': spotify_id,
                'profile_image_url': profile_image_url
            }
            response = supabase.table('users').insert(new_user).execute()
            print(f"✅ Novo usuário criado: {display_name}")
            return response.data[0]
    except Exception as e:
        print(f'❌ Erro ao obter ou criar usuário: {e}')
        return None

def update_user_with_spotify(auth_id: str, spotify_id: str, display_name: str, email: str = None, profile_image_url: str = None):
    """
    Atualiza um usuário existente com dados do Spotify.
    Retorna um dicionário com sucesso/erro.
    """
    try:
        # Verificar se este spotify_id já está vinculado a outro usuário
        existing_user = user_with_spotify_id_exists(spotify_id, exclude_auth_id=auth_id)
        
        if existing_user:
            # spotify_id já existe para outro usuário
            print(f"❌ Spotify ID já vinculado ao usuário: {existing_user['email']}")
            return {
                'success': False,
                'error': 'Esta conta Spotify já está vinculada a outro usuário',
                'existing_user_email': existing_user['email']
            }
        
        update_data = {
            'spotify_id': spotify_id,
            'display_name': display_name,
        }
        if email:
            update_data['email'] = email
        if profile_image_url:
            update_data['profile_image_url'] = profile_image_url
        
        response = supabase.table('users').update(update_data).eq('auth_id', auth_id).execute()
        print(f"✅ Usuário atualizado com dados do Spotify: {display_name}")
        return {
            'success': True,
            'user': response.data[0] if response.data else None
        }
    except Exception as e:
        print(f'❌ Erro ao atualizar usuário: {e}')
        return {
            'success': False,
            'error': str(e)
        }

def get_user_by_auth_id(auth_id: str):
    """
    Obtém um usuário pelo auth_id.
    """
    try:
        response = supabase.table('users').select('*').eq('auth_id', auth_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'❌ Erro ao obter usuário: {e}')
        return None

def get_user_by_spotify_id(spotify_id: str):
    """
    Obtém um usuário pelo spotify_id.
    """
    try:
        response = supabase.table('users').select('*').eq('spotify_id', spotify_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'❌ Erro ao obter usuário por spotify_id: {e}')
        return None

# --- Funções de Playlists ---

def save_selected_playlist(user_id: str, spotify_playlist_id: str, playlist_name: str, playlist_image_url: str = None):
    """
    Salva a playlist selecionada pelo usuário.
    """
    try:
        playlist_data = {
            'user_id': user_id,
            'spotify_playlist_id': spotify_playlist_id,
            'playlist_name': playlist_name,
            'playlist_image_url': playlist_image_url
        }
        response = supabase.table('playlists').upsert(playlist_data).execute()
        print(f"✅ Playlist salva: {playlist_name}")
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'❌ Erro ao salvar playlist: {e}')
        return None

def get_user_playlists(user_id: str):
    """
    Obtém todas as playlists salvas do usuário.
    """
    try:
        response = supabase.table('playlists').select('*').eq('user_id', user_id).execute()
        return response.data
    except Exception as e:
        print(f'❌ Erro ao obter playlists do usuário: {e}')
        return []

def get_last_selected_playlist(user_id: str):
    """
    Obtém a última playlist selecionada pelo usuário.
    """
    try:
        response = supabase.table('playlists').select('*').eq('user_id', user_id).order('selected_at', desc=True).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'❌ Erro ao obter última playlist: {e}')
        return None

# --- Funções de Histórico de Fila ---

def save_to_queue_history(user_id: str, spotify_track_id: str, track_name: str, track_artist: str, playlist_id: str = None):
    """
    Salva uma música adicionada à fila no histórico.
    """
    try:
        history_data = {
            'user_id': user_id,
            'spotify_track_id': spotify_track_id,
            'track_name': track_name,
            'track_artist': track_artist,
            'playlist_id': playlist_id
        }
        response = supabase.table('queue_history').insert(history_data).execute()
        print(f"✅ Música adicionada ao histórico: {track_name}")
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'❌ Erro ao salvar no histórico de fila: {e}')
        return None

def get_user_queue_history(user_id: str, limit: int = 50):
    """
    Obtém o histórico de músicas adicionadas à fila do usuário.
    """
    try:
        response = supabase.table('queue_history').select('*').eq('user_id', user_id).order('added_at', desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        print(f'❌ Erro ao obter histórico de fila: {e}')
        return []

def get_recent_tracks(user_id: str, days: int = 7):
    """
    Obtém as músicas adicionadas nos últimos N dias.
    """
    try:
        from datetime import datetime, timedelta
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        response = supabase.table('queue_history').select('*').eq('user_id', user_id).gte('added_at', start_date).order('added_at', desc=True).execute()
        return response.data
    except Exception as e:
        print(f'❌ Erro ao obter tracks recentes: {e}')
        return []
    
def user_with_spotify_id_exists(spotify_id: str, exclude_auth_id: str = None):
    """
    Verifica se um spotify_id já está vinculado a outro usuário.
    Se exclude_auth_id for fornecido, ignora esse usuário na busca.
    """
    try:
        response = supabase.table('users').select('*').eq('spotify_id', spotify_id).execute()
        
        if response.data:
            for user in response.data:
                if exclude_auth_id is None or user['auth_id'] != exclude_auth_id:
                    return user
        return None
    except Exception as e:
        print(f'❌ Erro ao verificar spotify_id: {e}')
        return None