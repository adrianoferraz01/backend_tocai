import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Configurar cliente Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Funções de Usuário ---

def get_or_create_user(spotify_id: str, display_name: str, email: str = None, profile_image_url: str = None):
    """
    Obtém ou cria um usuário no Supabase baseado no spotify_id.
    """
    try:
        # Tenta buscar o usuário existente
        response = supabase.table('users').select('*').eq('spotify_id', spotify_id).execute()
        
        if response.data:
            # Usuário já existe, retorna o primeiro resultado
            return response.data[0]
        else:
            # Usuário não existe, cria um novo
            new_user = {
                'spotify_id': spotify_id,
                'display_name': display_name,
                'email': email,
                'profile_image_url': profile_image_url
            }
            response = supabase.table('users').insert(new_user).execute()
            return response.data[0]
    except Exception as e:
        print(f'Erro ao obter ou criar usuário: {e}')
        return None

def update_user(user_id: str, **kwargs):
    """
    Atualiza informações do usuário.
    """
    try:
        response = supabase.table('users').update(kwargs).eq('id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Erro ao atualizar usuário: {e}')
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
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Erro ao salvar playlist: {e}')
        return None

def get_user_playlists(user_id: str):
    """
    Obtém todas as playlists salvas do usuário.
    """
    try:
        response = supabase.table('playlists').select('*').eq('user_id', user_id).execute()
        return response.data
    except Exception as e:
        print(f'Erro ao obter playlists do usuário: {e}')
        return []

def get_last_selected_playlist(user_id: str):
    """
    Obtém a última playlist selecionada pelo usuário.
    """
    try:
        response = supabase.table('playlists').select('*').eq('user_id', user_id).order('selected_at', desc=True).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Erro ao obter última playlist: {e}')
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
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Erro ao salvar no histórico de fila: {e}')
        return None

def get_user_queue_history(user_id: str, limit: int = 50):
    """
    Obtém o histórico de músicas adicionadas à fila do usuário.
    """
    try:
        response = supabase.table('queue_history').select('*').eq('user_id', user_id).order('added_at', desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        print(f'Erro ao obter histórico de fila: {e}')
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
        print(f'Erro ao obter tracks recentes: {e}')
        return []