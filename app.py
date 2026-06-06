import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'wizard_chess_secret_vfinal')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

SPELLS = [
    {'id': 'avada', 'name': 'Avada Kedavra', 'rarity': 'Legendary', 'icon': 'fa-solid fa-bolt', 'type': 'enemy', 'desc': 'Click an enemy piece to destroy it.'},
    {'id': 'time', 'name': 'Time-Turner', 'rarity': 'Legendary', 'icon': 'fa-solid fa-hourglass-half', 'type': 'instant', 'desc': 'Rewind the board.'},
    {'id': 'imperio', 'name': 'Imperio', 'rarity': 'Rare', 'icon': 'fa-solid fa-eye', 'type': 'drag_enemy', 'desc': 'Select enemy, then destination.'},
    {'id': 'sectum', 'name': 'Sectumsempra', 'rarity': 'Rare', 'icon': 'fa-solid fa-droplet', 'type': 'enemy', 'desc': 'Demote an enemy piece to a Pawn.'},
    {'id': 'fiendfyre', 'name': 'Fiendfyre', 'rarity': 'Rare', 'icon': 'fa-solid fa-fire', 'type': 'any', 'desc': 'Destroy a 3x3 square area.'},
    {'id': 'accio', 'name': 'Accio', 'rarity': 'Common', 'icon': 'fa-solid fa-magnet', 'type': 'drag_own', 'desc': 'Move your piece up to 2 squares.'},
    {'id': 'leviosa', 'name': 'Wingardium Leviosa', 'rarity': 'Common', 'icon': 'fa-solid fa-feather', 'type': 'drag_own', 'desc': 'Move to adjacent empty square.'},
    {'id': 'alohomora', 'name': 'Alohomora', 'rarity': 'Common', 'icon': 'fa-solid fa-key', 'type': 'drag_own', 'desc': 'Move to any empty square on your half.'},
    {'id': 'expelliarmus', 'name': 'Expelliarmus', 'rarity': 'Common', 'icon': 'fa-solid fa-wand-magic-sparkles', 'type': 'instant', 'desc': 'Keep your turn and move again.'},
    {'id': 'protego', 'name': 'Protego', 'rarity': 'Common', 'icon': 'fa-solid fa-shield-halved', 'type': 'own_pawn', 'desc': 'Promote your Pawn to a Knight.'},
]

SPELL_THEME = {
    'avada': {'bg': 'linear-gradient(180deg, #271111 0%, #140707 100%)', 'border': '#ff6b6b', 'glow': 'rgba(255, 107, 107, 0.25)', 'text': '#ffd0d0'},
    'time': {'bg': 'linear-gradient(180deg, #20183a 0%, #0f1024 100%)', 'border': '#9d7bff', 'glow': 'rgba(157, 123, 255, 0.28)', 'text': '#ddd5ff'},
    'imperio': {'bg': 'linear-gradient(180deg, #14302a 0%, #071613 100%)', 'border': '#57d6c3', 'glow': 'rgba(87, 214, 195, 0.24)', 'text': '#d4fff7'},
    'sectum': {'bg': 'linear-gradient(180deg, #2f1220 0%, #170810 100%)', 'border': '#ff7ac8', 'glow': 'rgba(255, 122, 200, 0.24)', 'text': '#ffd7ef'},
    'fiendfyre': {'bg': 'linear-gradient(180deg, #3a2208 0%, #190c02 100%)', 'border': '#ff9f43', 'glow': 'rgba(255, 159, 67, 0.28)', 'text': '#ffe2bd'},
    'accio': {'bg': 'linear-gradient(180deg, #10263a 0%, #07111a 100%)', 'border': '#4db9ff', 'glow': 'rgba(77, 185, 255, 0.24)', 'text': '#d7f0ff'},
    'leviosa': {'bg': 'linear-gradient(180deg, #224023 0%, #0e1a10 100%)', 'border': '#7ee081', 'glow': 'rgba(126, 224, 129, 0.24)', 'text': '#ddffde'},
    'alohomora': {'bg': 'linear-gradient(180deg, #3b3410 0%, #191507 100%)', 'border': '#ffd36b', 'glow': 'rgba(255, 211, 107, 0.24)', 'text': '#fff2cc'},
    'expelliarmus': {'bg': 'linear-gradient(180deg, #39214a 0%, #170e20 100%)', 'border': '#d48cff', 'glow': 'rgba(212, 140, 255, 0.24)', 'text': '#f0d8ff'},
    'protego': {'bg': 'linear-gradient(180deg, #19354a 0%, #08131d 100%)', 'border': '#6fd3ff', 'glow': 'rgba(111, 211, 255, 0.24)', 'text': '#d9f5ff'},
}

ROOMS = {}


def fen_side_to_move(fen: str) -> str:
    try:
        return fen.split()[1]
    except Exception:
        return 'w'


def switch_turn_in_fen(fen: str) -> str:
    parts = fen.split(' ')
    if len(parts) >= 2:
        parts[1] = 'b' if parts[1] == 'w' else 'w'
    return ' '.join(parts) if parts else fen


def fresh_hand():
    legendary = [s for s in SPELLS if s['rarity'] == 'Legendary']
    rare = [s for s in SPELLS if s['rarity'] == 'Rare']
    common = [s for s in SPELLS if s['rarity'] == 'Common']
    hand = random.sample(legendary, 1) + random.sample(rare, 2) + random.sample(common, 3)
    random.shuffle(hand)
    return hand


def get_room(room_id: str):
    if room_id not in ROOMS:
        ROOMS[room_id] = {
            'fen': START_FEN,
            'turn': 'w',
            'history': [START_FEN],
            'player_ids': {'w': None, 'b': None},
            'player_names': {'w': '', 'b': ''},
            'hands': {'w': None, 'b': None},
            'used': {'w': set(), 'b': set()},
            'log': [],
            'game_over': False,
            'winner': None,
        }
    return ROOMS[room_id]


def side_for_player(room, player_id):
    if room['player_ids']['w'] == player_id:
        return 'w'
    if room['player_ids']['b'] == player_id:
        return 'b'
    return None


def room_started(room):
    return room['player_ids']['w'] is not None and room['player_ids']['b'] is not None


def room_snapshot(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        return {}
    return {
        'room': room_id,
        'fen': room['fen'],
        'turn': room['turn'],
        'started': room_started(room),
        'game_over': room['game_over'],
        'winner': room['winner'],
        'names': room['player_names'],
        'history_length': len(room['history']),
        'used': {
            'w': list(room['used']['w']),
            'b': list(room['used']['b']),
        },
        'log': room['log'],
    }


def sync_room(room_id: str):
    socketio.emit('state_sync', room_snapshot(room_id), to=room_id)


@app.route('/')
def index():
    return render_template_string(HTML_PAYLOAD)


@socketio.on('join_room')
def handle_join(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    if not room_id or not player_id:
        return

    room = get_room(room_id)

    color = 's'
    if room['player_ids']['w'] == player_id:
        color = 'w'
    elif room['player_ids']['b'] == player_id:
        color = 'b'
    elif room['player_ids']['w'] is None:
        color = 'w'
        room['player_ids']['w'] = player_id
    elif room['player_ids']['b'] is None:
        color = 'b'
        room['player_ids']['b'] = player_id

    join_room(room_id)

    if color in ('w', 'b') and room['hands'][color] is None:
        room['hands'][color] = fresh_hand()

    emit('role_assigned', {
        'color': color,
        'hand': room['hands'].get(color, []) if color in ('w', 'b') else [],
        'used_spells': list(room['used'][color]) if color in ('w', 'b') else [],
        'snapshot': room_snapshot(room_id),
    }, to=request.sid)

    sync_room(room_id)


@socketio.on('set_name')
def handle_set_name(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    name = (data.get('name') or '').strip()[:24]
    if not room_id or not player_id or not name:
        return

    room = ROOMS.get(room_id)
    if not room:
        return

    color = side_for_player(room, player_id)
    if color not in ('w', 'b'):
        return

    room['player_names'][color] = name
    emit('name_saved', {'name': name, 'color': color}, to=request.sid)
    sync_room(room_id)


@socketio.on('standard_move')
def handle_standard_move(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    base_fen = data.get('base_fen')
    new_fen = data.get('fen')
    san = data.get('san', 'MOVE')

    if not room_id or room_id not in ROOMS or not new_fen:
        return

    room = ROOMS[room_id]
    if room['game_over']:
        return

    color = side_for_player(room, player_id)
    if color not in ('w', 'b') or room['turn'] != color:
        return

    if base_fen and base_fen != room['fen']:
        sync_room(room_id)
        return

    room['fen'] = new_fen
    room['turn'] = fen_side_to_move(new_fen)
    room['history'].append(new_fen)
    room['log'].append({'color': color, 'text': san, 'is_spell': False})
    sync_room(room_id)


@socketio.on('spell_effect')
def handle_spell_effect(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    spell_id = data.get('spell_id')
    base_fen = data.get('base_fen')
    new_fen = data.get('fen')
    log_text = data.get('log', '') or 'SPELL'
    consume_turn = bool(data.get('consume_turn', True))

    if not room_id or room_id not in ROOMS or not spell_id:
        return

    room = ROOMS[room_id]
    if room['game_over']:
        return

    color = side_for_player(room, player_id)
    if color not in ('w', 'b') or room['turn'] != color:
        return

    if spell_id in room['used'][color]:
        return

    if base_fen and base_fen != room['fen']:
        sync_room(room_id)
        return

    if spell_id == 'time':
        if len(room['history']) < 2:
            return
        new_fen = room['history'][-2]
        consume_turn = True

    if spell_id == 'expelliarmus':
        new_fen = room['fen']
        consume_turn = False

    if new_fen is None:
        return

    room['used'][color].add(spell_id)
    room['fen'] = new_fen
    if consume_turn:
        room['turn'] = fen_side_to_move(new_fen)
    room['history'].append(new_fen)
    room['log'].append({'color': color, 'text': log_text, 'is_spell': True, 'spell_id': spell_id})
    sync_room(room_id)


@socketio.on('resign_game')
def handle_resign(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    if room['game_over']:
        return

    color = side_for_player(room, player_id)
    if color not in ('w', 'b'):
        return

    winner = 'b' if color == 'w' else 'w'
    room['game_over'] = True
    room['winner'] = winner
    room['log'].append({'color': color, 'text': 'resigned', 'is_spell': False})
    sync_room(room_id)
    socketio.emit('game_over', {
        'room': room_id,
        'winner': winner,
        'winner_name': room['player_names'].get(winner) or ('White' if winner == 'w' else 'Black'),
        'by': color,
        'by_name': room['player_names'].get(color) or ('White' if color == 'w' else 'Black'),
        'reason': 'resign',
    }, to=room_id)


HTML_PAYLOAD = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Wizard's Chess</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #302e2b;
            color: #ffffff;
            overscroll-behavior: none;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        .bg-panel { background-color: #262421; }
        .text-muted { color: #a7a6a2; }
        .sq-light { background-color: #ebecd0; }
        .sq-dark { background-color: #739552; }
        .sq-highlight { position: absolute; inset: 0; background-color: rgba(255, 255, 51, 0.4); pointer-events: none; }
        .sq-selected { position: absolute; inset: 0; background-color: rgba(20, 85, 30, 0.5); pointer-events: none; }
        .move-dot { width: 32%; height: 32%; border-radius: 50%; background-color: rgba(0, 0, 0, 0.25); position: absolute; pointer-events: none; }
        .capture-dot { width: 85%; height: 85%; border-radius: 50%; border: 6px solid rgba(0, 0, 0, 0.25); position: absolute; background: transparent; pointer-events: none; }
        .piece {
            width: 100%; height: 100%; background-size: contain; background-repeat: no-repeat; background-position: center;
            position: relative; z-index: 10; cursor: pointer; transition: transform 0.05s ease; user-select: none; -webkit-user-drag: none;
        }
        .piece:active { transform: scale(1.08); }
        .wP { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png'); }
        .wN { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wn.png'); }
        .wB { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wb.png'); }
        .wR { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wr.png'); }
        .wQ { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wq.png'); }
        .wK { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wk.png'); }
        .bP { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png'); }
        .bN { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bn.png'); }
        .bB { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bb.png'); }
        .bR { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/br.png'); }
        .bQ { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bq.png'); }
        .bK { background-image: url('https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bk.png'); }
        .mini-piece { width: 18px; height: 18px; display: inline-block; background-size: contain; margin-right: -4px; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #262421; }
        ::-webkit-scrollbar-thumb { background: #4b4845; border-radius: 4px; }
        .spell-card { transition: all 0.2s; position: relative; overflow: hidden; }
        .spell-card::before { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,0.08) 0%, transparent 100%); pointer-events: none; }
        .spell-card.active { transform: translateY(-4px) scale(1.01); }
        .spell-card.used { opacity: 0.25; filter: grayscale(1); pointer-events: none; }
        .overlay {
            position: absolute; inset: 0; background: rgba(0,0,0,0.7); display: flex; flex-direction: column; justify-content: center; align-items: center;
            z-index: 50; backdrop-filter: blur(4px);
        }
        .board-wrapper { width: 100%; height: 100%; max-width: 85vh; display: flex; flex-direction: column; justify-content: center; margin: 0 auto; }
    </style>
</head>
<body class="flex flex-col lg:flex-row h-screen">
    <div class="flex-grow flex flex-col justify-center p-2 lg:p-4 bg-[#302e2b] overflow-hidden">
        <div class="board-wrapper gap-1.5 lg:gap-3 relative">
            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-[#1f1e1b] rounded flex items-center justify-center overflow-hidden border border-[#3f3e3b]">
                        <img src="https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png" class="w-8 h-8 object-contain" id="opp-avatar">
                    </div>
                    <div>
                        <div class="font-bold text-sm tracking-wide text-white" id="opp-name">Opponent</div>
                        <div class="flex items-center mt-0.5 min-h-[18px]" id="captured-top"></div>
                    </div>
                </div>
                <div class="text-xs font-mono font-bold bg-[#1f1e1b] text-muted px-3 py-2 rounded" id="opp-status">Waiting</div>
            </div>

            <div class="w-full aspect-square rounded shadow-2xl overflow-hidden relative border-4 border-[#262421]">
                <div id="board-grid" class="w-full h-full grid grid-cols-8 grid-rows-8 select-none bg-[#739552] transition-transform duration-150"></div>

                <div id="waiting-overlay" class="overlay hidden">
                    <div class="bg-[#262421] border border-[#3f3e3b] p-6 rounded-xl text-center max-w-[85%] shadow-2xl">
                        <h2 class="text-xl font-bold mb-2 text-white"><i class="fa-solid fa-chess-knight text-[#81b64c] mr-2"></i>Match Lobby</h2>
                        <p class="text-sm text-muted mb-4">Send this link to a friend to start the match.</p>
                        <div class="flex gap-2">
                            <input type="text" id="share-link" readonly class="w-full bg-[#141312] border border-[#3f3e3b] text-white p-3 rounded-lg text-xs font-mono focus:outline-none">
                            <button onclick="copyLink()" class="bg-[#81b64c] hover:bg-[#a3d160] text-black font-extrabold px-4 rounded-lg text-sm transition"><i class="fa-solid fa-copy"></i></button>
                        </div>
                    </div>
                </div>

                <div id="spell-banner" class="hidden absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-white px-6 py-4 rounded-xl font-bold text-center z-50 shadow-[0_0_30px_rgba(168,85,247,0.5)] border border-purple-300 w-[85%] max-w-[320px]">
                    <div id="spell-banner-title" class="text-xl mb-1 drop-shadow-md">SPELL</div>
                    <div id="spell-banner-desc" class="text-sm font-medium text-purple-100 mb-4">Action</div>
                    <button onclick="cancelSpell()" class="text-sm bg-black bg-opacity-40 hover:bg-opacity-60 px-4 py-2 rounded-lg w-full transition uppercase tracking-wider font-bold">Cancel</button>
                </div>

                <div id="name-overlay" class="overlay hidden">
                    <div class="bg-[#262421] border border-[#3f3e3b] p-6 rounded-xl text-center max-w-[85%] shadow-2xl w-[92%] max-w-[360px]">
                        <h2 class="text-xl font-bold mb-2 text-white"><i class="fa-solid fa-id-card text-[#81b64c] mr-2"></i>Choose Your Name</h2>
                        <p class="text-sm text-muted mb-4">This name will be shown in the match.</p>
                        <input id="name-input" type="text" maxlength="24" class="w-full bg-[#141312] border border-[#3f3e3b] text-white p-3 rounded-lg text-sm focus:outline-none mb-3" placeholder="Enter a name">
                        <button onclick="submitName()" class="w-full bg-[#81b64c] hover:bg-[#a3d160] text-black font-extrabold px-4 py-3 rounded-lg text-sm transition">Start Playing</button>
                    </div>
                </div>

                <div id="game-over-overlay" class="overlay hidden">
                    <div class="bg-[#262421] border border-[#3f3e3b] p-6 rounded-xl text-center max-w-[85%] shadow-2xl w-[92%] max-w-[360px]">
                        <h2 class="text-2xl font-extrabold mb-2 text-white"><i class="fa-solid fa-trophy text-[#81b64c] mr-2"></i>Game Over</h2>
                        <p id="game-over-text" class="text-sm text-muted mb-4">The match has ended.</p>
                        <button onclick="resignGame()" class="w-full bg-[#ff5d5d] hover:bg-[#ff7777] text-black font-extrabold px-4 py-3 rounded-lg text-sm transition">Close</button>
                    </div>
                </div>
            </div>

            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-[#1f1e1b] rounded flex items-center justify-center overflow-hidden border border-[#3f3e3b]">
                        <img src="https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png" class="w-8 h-8 object-contain" id="my-avatar">
                    </div>
                    <div>
                        <div class="font-bold text-sm tracking-wide text-white" id="my-name">You</div>
                        <div class="flex items-center mt-0.5 min-h-[18px]" id="captured-bottom"></div>
                    </div>
                </div>
                <div class="text-xs font-mono font-bold bg-[#81b64c] text-black px-3 py-2 rounded" id="my-status">Thinking</div>
            </div>
        </div>
    </div>

    <div class="w-full lg:w-[380px] xl:w-[420px] bg-[#262421] border-l border-[#3f3e3b] flex flex-col h-[35vh] lg:h-full z-10 shadow-2xl flex-shrink-0">
        <div class="p-4 border-b border-[#3f3e3b] bg-[#211f1c]">
            <div class="flex justify-between items-center mb-3">
                <h3 class="font-bold text-xs text-muted uppercase tracking-widest"><i class="fa-solid fa-book-journal-whills mr-2"></i>Your Grimoire</h3>
                <span id="turn-indicator" class="text-[10px] font-bold px-2 py-1 rounded bg-[#1f1e1b] text-muted">WAITING</span>
            </div>
            <div id="spells-container" class="flex lg:grid lg:grid-cols-3 gap-2 overflow-x-auto lg:overflow-y-auto lg:max-h-[220px] custom-scrollbar pb-2 lg:pb-0 pr-1"></div>
        </div>

        <div class="px-4 py-3 border-b border-[#3f3e3b] flex justify-between items-center bg-[#262421]">
            <span class="font-bold text-xs text-muted uppercase tracking-widest"><i class="fa-solid fa-list-ul mr-2"></i>Match Log</span>
            <button onclick="resignGame()" class="text-xs text-red-400 hover:text-red-300 transition font-bold"><i class="fa-solid fa-flag mr-1"></i>Resign</button>
        </div>
        <div class="flex-grow overflow-y-auto p-4 custom-scrollbar bg-[#1f1e1b] font-mono text-sm shadow-inner" id="move-history"></div>
    </div>

<script>
    const socket = io();

    let playerId = localStorage.getItem('wizard_chess_id');
    if (!playerId) {
        playerId = Math.random().toString(36).substring(2, 15);
        localStorage.setItem('wizard_chess_id', playerId);
    }

    const room = (() => {
        const params = new URLSearchParams(location.search);
        let r = params.get('room');
        if (!r) {
            r = Math.random().toString(36).slice(2, 9);
            history.replaceState({}, '', `${location.pathname}?room=${r}`);
        }
        return r;
    })();

    document.getElementById('share-link').value = location.href;
    function copyLink() {
        const input = document.getElementById('share-link');
        input.select();
        input.setSelectionRange(0, 99999);
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(location.href).catch(() => document.execCommand('copy'));
        } else {
            document.execCommand('copy');
        }
    }

    const sfxMove = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3');
    const sfxCapture = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3');
    const sfxSpell = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3');
    const sfxStart = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/game-start.mp3');

    let game = new Chess();
    let myColor = null;
    let myHand = [];
    let usedSpells = new Set();
    let isFlipped = false;
    let gameReady = false;
    let gameOver = false;
    let selectedSquare = null;
    let activeSpell = null;
    let spellSourceSq = null;
    let currentNames = { w: '', b: '' };
    let currentLog = [];

    const SPELL_THEMES = {
        avada: { bg: 'linear-gradient(180deg,#281111,#130707)', border: '#ff6b6b', glow: 'rgba(255,107,107,0.22)', icon: '#ffd0d0' },
        time: { bg: 'linear-gradient(180deg,#20183a,#0f1024)', border: '#9d7bff', glow: 'rgba(157,123,255,0.24)', icon: '#ddd5ff' },
        imperio: { bg: 'linear-gradient(180deg,#14302a,#071613)', border: '#57d6c3', glow: 'rgba(87,214,195,0.22)', icon: '#d4fff7' },
        sectum: { bg: 'linear-gradient(180deg,#2f1220,#170810)', border: '#ff7ac8', glow: 'rgba(255,122,200,0.22)', icon: '#ffd7ef' },
        fiendfyre: { bg: 'linear-gradient(180deg,#3a2208,#190c02)', border: '#ff9f43', glow: 'rgba(255,159,67,0.24)', icon: '#ffe2bd' },
        accio: { bg: 'linear-gradient(180deg,#10263a,#07111a)', border: '#4db9ff', glow: 'rgba(77,185,255,0.22)', icon: '#d7f0ff' },
        leviosa: { bg: 'linear-gradient(180deg,#224023,#0e1a10)', border: '#7ee081', glow: 'rgba(126,224,129,0.22)', icon: '#ddffde' },
        alohomora: { bg: 'linear-gradient(180deg,#3b3410,#191507)', border: '#ffd36b', glow: 'rgba(255,211,107,0.22)', icon: '#fff2cc' },
        expelliarmus: { bg: 'linear-gradient(180deg,#39214a,#170e20)', border: '#d48cff', glow: 'rgba(212,140,255,0.22)', icon: '#f0d8ff' },
        protego: { bg: 'linear-gradient(180deg,#19354a,#08131d)', border: '#6fd3ff', glow: 'rgba(111,211,255,0.22)', icon: '#d9f5ff' },
    };

    function myNameFromState() {
        if (!myColor || myColor === 's') return 'You';
        const n = currentNames[myColor];
        return n ? `You (${n})` : (myColor === 'w' ? 'You (White)' : 'You (Black)');
    }

    function oppNameFromState() {
        if (!myColor || myColor === 's') return 'Opponent';
        const opp = myColor === 'w' ? 'b' : 'w';
        const n = currentNames[opp];
        return n ? n : (opp === 'w' ? 'Opponent (White)' : 'Opponent (Black)');
    }

    function buildBoardDOM() {
        const boardEl = document.getElementById('board-grid');
        boardEl.innerHTML = '';
        const files = ['a','b','c','d','e','f','g','h'];
        const ranks = ['8','7','6','5','4','3','2','1'];

        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                const sqName = files[f] + ranks[r];
                const isLight = (r + f) % 2 === 0;
                const sqEl = document.createElement('div');
                sqEl.className = `relative flex items-center justify-center ${isLight ? 'sq-light' : 'sq-dark'}`;
                sqEl.id = `sq-${sqName}`;
                sqEl.dataset.sq = sqName;
                sqEl.onclick = () => handleSquareClick(sqName);

                const highlight = document.createElement('div');
                highlight.id = `hl-${sqName}`;
                highlight.style.display = 'none';

                const dot = document.createElement('div');
                dot.id = `dot-${sqName}`;
                dot.style.display = 'none';

                const piece = document.createElement('div');
                piece.id = `piece-${sqName}`;
                piece.className = 'piece';
                piece.style.display = 'none';

                sqEl.appendChild(highlight);
                sqEl.appendChild(dot);
                sqEl.appendChild(piece);
                boardEl.appendChild(sqEl);
            }
        }
    }

    function setBoardFlip() {
        const boardEl = document.getElementById('board-grid');
        boardEl.classList.toggle('rotate-180', isFlipped);
    }

    function isMyTurn() {
        return myColor && myColor !== 's' && gameReady && !gameOver && game.turn() === myColor;
    }

    function clearSelections() {
        selectedSquare = null;
        activeSpell = null;
        spellSourceSq = null;
        document.getElementById('spell-banner').classList.add('hidden');
    }

    function switchTurnInFen(fen) {
        const parts = fen.split(' ');
        if (parts.length > 1) parts[1] = parts[1] === 'w' ? 'b' : 'w';
        if (parts.length > 3) parts[3] = '-';
        return parts.join(' ');
    }

    function submitName() {
        const input = document.getElementById('name-input');
        const name = (input.value || '').trim();
        if (!name) return;
        localStorage.setItem('wizard_chess_name', name);
        socket.emit('set_name', { room, player_id: playerId, name });
        document.getElementById('name-overlay').classList.add('hidden');
    }

    function openNameOverlay() {
        document.getElementById('name-overlay').classList.remove('hidden');
        const input = document.getElementById('name-input');
        input.value = localStorage.getItem('wizard_chess_name') || '';
        setTimeout(() => input.focus(), 50);
    }

    function resignGame() {
        if (!myColor || myColor === 's' || gameOver) return;
        socket.emit('resign_game', { room, player_id: playerId });
    }

    function handleSquareClick(sq) {
        if (!gameReady || gameOver || myColor === 's' || !isMyTurn()) return;

        if (activeSpell) {
            processSpellClick(sq);
            return;
        }

        const p = game.get(sq);
        if (p && p.color === myColor) {
            selectedSquare = selectedSquare === sq ? null : sq;
            updateUI();
            return;
        }

        if (selectedSquare) {
            const temp = new Chess(game.fen());
            const move = temp.move({ from: selectedSquare, to: sq, promotion: 'q' });
            if (move) {
                socket.emit('standard_move', {
                    room,
                    player_id: playerId,
                    base_fen: game.fen(),
                    from: move.from,
                    to: move.to,
                    san: move.san,
                    fen: temp.fen(),
                });
            }
            clearSelections();
            updateUI();
        }
    }

    function processSpellClick(sq) {
        const p = game.get(sq);
        const opp = myColor === 'w' ? 'b' : 'w';
        const baseFen = game.fen();

        const commitSpellEffect = (newFen, consumeTurn, customLog) => {
            usedSpells.add(activeSpell.id);
            socket.emit('spell_effect', {
                room,
                player_id: playerId,
                base_fen: baseFen,
                spell_id: activeSpell.id,
                name: activeSpell.name,
                fen: newFen,
                consume_turn: consumeTurn,
                log: customLog || activeSpell.name.toUpperCase(),
            });
            clearSelections();
            updateUI();
        };

        switch (activeSpell.type) {
            case 'enemy': {
                if (p && p.color === opp && p.type !== 'k') {
                    const temp = new Chess(baseFen);
                    if (activeSpell.id === 'sectum') {
                        temp.remove(sq);
                        temp.put({ type: 'p', color: opp }, sq);
                    } else {
                        temp.remove(sq);
                    }
                    commitSpellEffect(temp.fen(), true, `${activeSpell.name.toUpperCase()} ${sq.toUpperCase()}`);
                }
                break;
            }
            case 'any': {
                const fileIdx = sq.charCodeAt(0);
                const rankIdx = parseInt(sq[1], 10);
                const temp = new Chess(baseFen);
                for (let f = fileIdx - 1; f <= fileIdx + 1; f++) {
                    for (let r = rankIdx - 1; r <= rankIdx + 1; r++) {
                        if (f < 97 || f > 104 || r < 1 || r > 8) continue;
                        const targetSq = String.fromCharCode(f) + r;
                        const tP = temp.get(targetSq);
                        if (tP && tP.type !== 'k') temp.remove(targetSq);
                    }
                }
                commitSpellEffect(temp.fen(), true, 'FIENDFYRE');
                break;
            }
            case 'own_pawn': {
                if (p && p.color === myColor && p.type === 'p') {
                    const temp = new Chess(baseFen);
                    temp.remove(sq);
                    temp.put({ type: 'n', color: myColor }, sq);
                    commitSpellEffect(temp.fen(), true, 'PROTEGO');
                }
                break;
            }
            case 'drag_own':
            case 'drag_enemy': {
                if (!spellSourceSq) {
                    const reqColor = activeSpell.type === 'drag_own' ? myColor : opp;
                    if (p && p.color === reqColor) {
                        spellSourceSq = sq;
                        updateUI();
                    }
                    return;
                }

                const source = spellSourceSq;
                const fDist = Math.abs(source.charCodeAt(0) - sq.charCodeAt(0));
                const rDist = Math.abs(parseInt(source[1], 10) - parseInt(sq[1], 10));
                const temp = new Chess(baseFen);

                if (activeSpell.id === 'accio' && (fDist > 2 || rDist > 2)) return;
                if (activeSpell.id === 'leviosa' && ((fDist > 1 || rDist > 1) || p)) return;
                if (activeSpell.id === 'alohomora') {
                    const isOwnHalf = myColor === 'w' ? parseInt(sq[1], 10) <= 4 : parseInt(sq[1], 10) >= 5;
                    if (!isOwnHalf || p) return;
                }

                if (activeSpell.id === 'imperio') {
                    temp.load(switchTurnInFen(baseFen));
                    const move = temp.move({ from: source, to: sq, promotion: 'q' });
                    if (move) {
                        commitSpellEffect(switchTurnInFen(temp.fen()), true, `IMPERIO: ${move.san}`);
                    } else {
                        spellSourceSq = null;
                        updateUI();
                    }
                    return;
                }

                const piece = temp.get(source);
                if (!piece) return;
                temp.remove(source);
                temp.remove(sq);
                temp.put(piece, sq);
                commitSpellEffect(temp.fen(), true, activeSpell.name.toUpperCase());
                break;
            }
        }
    }

    function cancelSpell() {
        selectedSquare = null;
        activeSpell = null;
        spellSourceSq = null;
        document.getElementById('spell-banner').classList.add('hidden');
        updateUI();
    }

    function renderLog(entries) {
        const hist = document.getElementById('move-history');
        hist.innerHTML = '';
        entries.forEach((entry, idx) => {
            const row = document.createElement('div');
            row.className = 'flex py-1.5 border-b border-[#3f3e3b] gap-2 items-start';
            const num = document.createElement('div');
            num.className = 'w-8 text-muted shrink-0';
            num.textContent = `${idx + 1}.`;
            const text = document.createElement('div');
            text.className = entry.is_spell ? 'text-purple-300 font-bold' : 'text-[#e3e3e3]';
            const label = entry.color === 'w' ? 'White' : 'Black';
            const icon = entry.is_spell ? '<i class="fa-solid fa-wand-magic-sparkles text-[10px] mr-1 text-purple-300"></i>' : '';
            text.innerHTML = `${icon}${label}: ${entry.text}`;
            row.appendChild(num);
            row.appendChild(text);
            hist.appendChild(row);
        });
        hist.scrollTop = hist.scrollHeight;
    }

    function calcMaterial() {
        const counts = { w: {p:0,n:0,b:0,r:0,q:0}, b: {p:0,n:0,b:0,r:0,q:0} };
        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                const p = game.get(String.fromCharCode(97 + f) + (r + 1));
                if (p) counts[p.color][p.type]++;
            }
        }
        const values = { p:1, n:3, b:3, r:5, q:9 };
        const base = { p:8, n:2, b:2, r:2, q:1 };
        let wScore = 0, bScore = 0;
        let capW = '', capB = '';
        ['q','r','b','n','p'].forEach(type => {
            const wMiss = base[type] - counts.w[type];
            const bMiss = base[type] - counts.b[type];
            for (let i = 0; i < bMiss; i++) { capW += `<div class="mini-piece b${type.toUpperCase()}"></div>`; wScore += values[type]; }
            for (let i = 0; i < wMiss; i++) { capB += `<div class="mini-piece w${type.toUpperCase()}"></div>`; bScore += values[type]; }
        });
        const bottomAdv = wScore > bScore ? (myColor === 'w' ? wScore - bScore : '') : (bScore > wScore ? (myColor === 'b' ? bScore - wScore : '') : '');
        const topAdv = wScore > bScore ? (myColor === 'b' ? wScore - bScore : '') : (bScore > wScore ? (myColor === 'w' ? bScore - wScore : '') : '');
        document.getElementById('captured-bottom').innerHTML = (myColor === 'w' ? capW : capB) + (bottomAdv ? `<span class="text-xs text-muted ml-1 font-bold">+${bottomAdv}</span>` : '');
        document.getElementById('captured-top').innerHTML = (myColor === 'w' ? capB : capW) + (topAdv ? `<span class="text-xs text-muted ml-1 font-bold">+${topAdv}</span>` : '');
    }

    function updateUI() {
        const turn = game.turn();
        const files = ['a','b','c','d','e','f','g','h'];
        const ranks = ['8','7','6','5','4','3','2','1'];
        const legalMoves = selectedSquare ? game.moves({ square: selectedSquare, verbose: true }) : [];

        for (const r of ranks) {
            for (const f of files) {
                const sq = f + r;
                const p = game.get(sq);
                const pieceEl = document.getElementById(`piece-${sq}`);
                const hlEl = document.getElementById(`hl-${sq}`);
                const dotEl = document.getElementById(`dot-${sq}`);
                if (!pieceEl || !hlEl || !dotEl) continue;

                if (p) {
                    pieceEl.className = `piece ${p.color}${p.type.toUpperCase()}`;
                    pieceEl.style.display = 'block';
                } else {
                    pieceEl.style.display = 'none';
                    pieceEl.className = 'piece';
                }

                hlEl.className = 'sq-highlight';
                hlEl.style.display = 'none';
                dotEl.style.display = 'none';

                if (sq === selectedSquare || sq === spellSourceSq) {
                    hlEl.className = 'sq-selected';
                    hlEl.style.display = 'block';
                }

                if (selectedSquare) {
                    const isTarget = legalMoves.find(m => m.to === sq);
                    if (isTarget) {
                        dotEl.className = p ? 'capture-dot' : 'move-dot';
                        dotEl.style.display = 'block';
                    }
                }
            }
        }

        const isMy = turn === myColor;
        const myStatus = document.getElementById('my-status');
        const oppStatus = document.getElementById('opp-status');
        const turnIndicator = document.getElementById('turn-indicator');

        if (gameReady && !gameOver) {
            turnIndicator.innerText = isMy ? 'YOUR TURN' : "OPPONENT'S TURN";
            turnIndicator.className = `text-[10px] font-bold px-2 py-1 rounded shadow ${isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
            myStatus.innerText = isMy ? 'Thinking' : 'Waiting';
            myStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow ${isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
            oppStatus.innerText = !isMy ? 'Thinking' : 'Waiting';
            oppStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow ${!isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
        }

        const handContainer = document.getElementById('spells-container');
        handContainer.innerHTML = '';

        if (myHand && myColor !== 's') {
            myHand.forEach(spell => {
                const isUsed = usedSpells.has(spell.id);
                const isActive = activeSpell && activeSpell.id === spell.id;
                const theme = SPELL_THEME[spell.id] || { bg: 'linear-gradient(180deg,#222,#111)', border: '#666', glow: 'rgba(255,255,255,0.1)', icon: '#fff' };
                const card = document.createElement('div');
                card.className = `spell-card min-w-[100px] lg:w-auto p-3 rounded-xl border flex flex-col items-center justify-center text-center shadow-lg ${isUsed ? 'used' : ''} ${isActive ? 'active' : ''}`;
                card.style.background = theme.bg;
                card.style.borderColor = theme.border;
                card.style.boxShadow = `0 0 0 1px ${theme.border}, 0 8px 18px rgba(0,0,0,0.25), 0 0 18px ${theme.glow}`;
                card.style.color = theme.icon;
                card.innerHTML = `
                    <div class="text-2xl mb-1 drop-shadow-md" style="color:${theme.icon}"><i class="${spell.icon}"></i></div>
                    <div class="text-[10px] font-extrabold leading-tight mb-1 text-white tracking-wide">${spell.name}</div>
                    <div class="text-[9px] text-muted leading-tight hidden lg:block">${spell.desc}</div>
                `;
                if (!isUsed && isMyTurn()) card.classList.add('cursor-pointer');
                card.onclick = () => {
                    if (isUsed || !isMyTurn()) return;
                    if (isActive) { cancelSpell(); return; }
                    if (spell.type === 'instant') {
                        socket.emit('spell_effect', {
                            room,
                            player_id: playerId,
                            base_fen: game.fen(),
                            spell_id: spell.id,
                            name: spell.name,
                            fen: game.fen(),
                            consume_turn: false,
                            log: spell.name.toUpperCase(),
                        });
                        usedSpells.add(spell.id);
                        updateUI();
                    } else {
                        selectedSquare = null;
                        activeSpell = spell;
                        spellSourceSq = null;
                        const banner = document.getElementById('spell-banner');
                        document.getElementById('spell-banner-title').innerHTML = `<i class="${spell.icon} mr-2"></i>${spell.name}`;
                        document.getElementById('spell-banner-desc').innerText = spell.desc;
                        const theme = SPELL_THEME[spell.id] || { bg: 'linear-gradient(180deg,#222,#111)', border: '#666' };
                        banner.style.background = theme.bg;
                        banner.style.borderColor = theme.border;
                        banner.classList.remove('hidden');
                        updateUI();
                    }
                };
                handContainer.appendChild(card);
            });
        }

        calcMaterial();
    }

    function applySnapshot(state) {
        if (!state || !state.fen) return;
        game.load(state.fen);
        currentNames = state.names || { w: '', b: '' };
        gameReady = !!state.started && !state.game_over;
        gameOver = !!state.game_over;
        if (gameOver) {
            document.getElementById('game-over-overlay').classList.remove('hidden');
            const winnerName = state.winner === 'w' ? (currentNames.w || 'White') : (currentNames.b || 'Black');
            document.getElementById('game-over-text').innerText = `${winnerName} wins.`;
        } else {
            document.getElementById('game-over-overlay').classList.add('hidden');
        }
        document.getElementById('waiting-overlay').classList.toggle('hidden', gameReady || gameOver);
        if (!localStorage.getItem('wizard_chess_name')) {
            document.getElementById('name-overlay').classList.toggle('hidden', false);
        }
        if (gameReady && !window.__startedOnce) {
            window.__startedOnce = true;
            sfxStart.play().catch(()=>{});
        }
        setBoardFlip();
        document.getElementById('my-name').innerText = myNameFromState();
        document.getElementById('opp-name').innerText = oppNameFromState();
        updateUI();
        renderLog(state.log || []);
    }

    socket.on('connect', () => {
        socket.emit('join_room', { room, player_id: playerId });
    });

    socket.on('role_assigned', (data) => {
        myColor = data.color;
        myHand = data.hand || [];
        usedSpells = new Set(data.used_spells || []);
        isFlipped = myColor === 'b';
        setBoardFlip();
        const snap = data.snapshot || {};
        if (snap.fen) game.load(snap.fen);
        currentNames = snap.names || currentNames;

        if (myColor === 'w') {
            document.getElementById('my-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png';
            document.getElementById('opp-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png';
        } else if (myColor === 'b') {
            document.getElementById('my-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png';
            document.getElementById('opp-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png';
        }

        buildBoardDOM();
        applySnapshot(snap);

        const savedName = (localStorage.getItem('wizard_chess_name') || '').trim();
        if (savedName) {
            socket.emit('set_name', { room, player_id: playerId, name: savedName });
        } else {
            openNameOverlay();
        }
    });

    socket.on('name_saved', (data) => {
        if (data && data.name) {
            localStorage.setItem('wizard_chess_name', data.name);
        }
        document.getElementById('name-overlay').classList.add('hidden');
        updateUI();
    });

    socket.on('state_sync', (state) => {
        applySnapshot(state);
    });

    socket.on('game_started', (state) => {
        if (state && state.fen) applySnapshot(state);
    });

    socket.on('game_over', (data) => {
        gameOver = true;
        document.getElementById('game-over-overlay').classList.remove('hidden');
        const winnerName = data.winner === 'w' ? (currentNames.w || 'White') : (currentNames.b || 'Black');
        document.getElementById('game-over-text').innerText = `${winnerName} wins by resign. Refresh to start a new room.`;
        updateUI();
    });

    document.getElementById('name-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitName();
    });

    buildBoardDOM();
    document.getElementById('my-name').innerText = 'You';
    document.getElementById('opp-name').innerText = 'Opponent';
    updateUI();
</script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'> SERVER ONLINE. PORT: {port}')
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
