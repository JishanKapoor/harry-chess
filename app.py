import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'wizard_chess_secret_v3')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

SPELLS = [
    {'id': 'avada', 'name': 'Avada Kedavra', 'rarity': 'Legendary', 'icon': '⚡', 'type': 'enemy', 'desc': 'Click an enemy piece to destroy it.'},
    {'id': 'time', 'name': 'Time-Turner', 'rarity': 'Legendary', 'icon': '⏳', 'type': 'instant', 'desc': 'Rewind the board to the previous state.'},
    {'id': 'imperio', 'name': 'Imperio', 'rarity': 'Rare', 'icon': '👁️', 'type': 'drag_enemy', 'desc': 'Select an enemy piece, then its destination.'},
    {'id': 'sectum', 'name': 'Sectumsempra', 'rarity': 'Rare', 'icon': '🩸', 'type': 'enemy', 'desc': 'Demote an enemy piece to a Pawn.'},
    {'id': 'fiendfyre', 'name': 'Fiendfyre', 'rarity': 'Rare', 'icon': '🔥', 'type': 'any', 'desc': 'Destroy a 3x3 square area.'},
    {'id': 'accio', 'name': 'Accio', 'rarity': 'Common', 'icon': '🧲', 'type': 'drag_own', 'desc': 'Move your piece up to 2 squares (ignores rules).'},
    {'id': 'leviosa', 'name': 'Wingardium Leviosa', 'rarity': 'Common', 'icon': '🪶', 'type': 'drag_own', 'desc': 'Move your piece to any adjacent empty square.'},
    {'id': 'alohomora', 'name': 'Alohomora', 'rarity': 'Common', 'icon': '🗝️', 'type': 'drag_own', 'desc': 'Move your piece to any empty square on your half.'},
    {'id': 'expelliarmus', 'name': 'Expelliarmus', 'rarity': 'Common', 'icon': '🪄', 'type': 'instant', 'desc': 'Keep your turn and move again.'},
    {'id': 'protego', 'name': 'Protego', 'rarity': 'Common', 'icon': '🛡️', 'type': 'own_pawn', 'desc': 'Promote one of your Pawns to a Knight.'},
]

ROOMS = {}
SID_TO_ROOM = {}

def opp(color: str) -> str:
    return 'b' if color == 'w' else 'w'

def fen_side_to_move(fen: str) -> str:
    try:
        return fen.split()[1]
    except Exception:
        return 'w'

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
            'players': {'w': None, 'b': None},
            'hands': {'w': None, 'b': None},
            'used': {'w': set(), 'b': set()},
            'sid_to_color': {},
        }
    return ROOMS[room_id]

def snapshot(room_id: str):
    room = ROOMS[room_id]
    return {
        'room': room_id,
        'fen': room['fen'],
        'turn': room['turn'],
        'white_connected': room['players']['w'] is not None,
        'black_connected': room['players']['b'] is not None,
        'started': room['players']['w'] is not None and room['players']['b'] is not None,
    }

def color_for_sid(room, sid):
    return room['sid_to_color'].get(sid)

@app.route('/')
def index():
    return render_template_string(HTML_PAYLOAD)

@socketio.on('join_room')
def handle_join(data):
    room_id = data['room'] if isinstance(data, dict) else str(data)
    room = get_room(room_id)

    if room['players']['w'] is None:
        color = 'w'
    elif room['players']['b'] is None:
        color = 'b'
    else:
        color = 's'

    join_room(room_id)
    SID_TO_ROOM[request.sid] = room_id

    if color in ('w', 'b'):
        room['players'][color] = request.sid
        room['sid_to_color'][request.sid] = color
        if room['hands'][color] is None:
            room['hands'][color] = fresh_hand()

    emit('role_assigned', {
        'color': color,
        'hand': room['hands'].get(color, []) if color in ('w', 'b') else [],
        'snapshot': snapshot(room_id),
    }, to=request.sid)

    emit('room_state', snapshot(room_id), room=room_id)
    if room['players']['w'] is not None and room['players']['b'] is not None:
        emit('game_ready', snapshot(room_id), room=room_id)

@socketio.on('standard_move')
def handle_standard_move(data):
    room_id = SID_TO_ROOM.get(request.sid)
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    color = color_for_sid(room, request.sid)
    if color not in ('w', 'b'):
        return

    if room['players']['w'] is None or room['players']['b'] is None:
        emit('action_denied', {'reason': 'Waiting for both players.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    if room['turn'] != color:
        emit('action_denied', {'reason': 'It is not your turn.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    base_fen = data.get('base_fen')
    new_fen = data.get('fen')
    if base_fen != room['fen']:
        emit('action_denied', {'reason': 'Board out of sync. Resyncing.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    if not new_fen:
        emit('action_denied', {'reason': 'Missing move data.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    room['fen'] = new_fen
    room['turn'] = fen_side_to_move(new_fen)
    room['history'].append(new_fen)

    emit('standard_move', {
        'from': data.get('from'),
        'to': data.get('to'),
        'san': data.get('san'),
        'color': color,
        'fen': room['fen'],
        'turn': room['turn'],
    }, room=room_id, include_self=False)

@socketio.on('spell_effect')
def handle_spell_effect(data):
    room_id = SID_TO_ROOM.get(request.sid)
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    color = color_for_sid(room, request.sid)
    if color not in ('w', 'b'):
        return

    if room['players']['w'] is None or room['players']['b'] is None:
        emit('action_denied', {'reason': 'Waiting for both players.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    if room['turn'] != color:
        emit('action_denied', {'reason': 'It is not your turn.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    spell_id = data.get('spell_id')
    if spell_id in room['used'][color]:
        emit('action_denied', {'reason': 'That spell has already been used.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    base_fen = data.get('base_fen')
    if base_fen != room['fen']:
        emit('action_denied', {'reason': 'Board out of sync. Resyncing.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    consume_turn = bool(data.get('consume_turn', True))
    new_fen = data.get('fen')

    if spell_id == 'time':
        if len(room['history']) < 2:
            emit('action_denied', {'reason': 'Not enough history to rewind.', 'snapshot': snapshot(room_id)}, to=request.sid)
            return
        # Rewind history
        room['history'].pop() # remove current
        new_fen = room['history'][-1]
        consume_turn = True
        
        # To make it the other player's turn correctly after a rewind, 
        # we let the FEN side to move dictate it.

    if spell_id == 'expelliarmus':
        consume_turn = False
        if not new_fen:
            new_fen = room['fen']

    if not new_fen:
        emit('action_denied', {'reason': 'Missing spell data.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    room['used'][color].add(spell_id)
    room['fen'] = new_fen
    if consume_turn:
        room['turn'] = fen_side_to_move(new_fen)
        
    if spell_id != 'time':
        room['history'].append(new_fen)

    emit('spell_effect', {
        'spell_id': spell_id,
        'name': data.get('name', spell_id),
        'fen': room['fen'],
        'consume_turn': consume_turn,
        'color': color,
        'turn': room['turn'],
        'log': data.get('log', ''),
    }, room=room_id, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    room_id = SID_TO_ROOM.pop(request.sid, None)
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    color = room['sid_to_color'].pop(request.sid, None)
    if color in ('w', 'b') and room['players'].get(color) == request.sid:
        room['players'][color] = None

    try:
        leave_room(room_id)
    except Exception:
        pass

    emit('room_state', snapshot(room_id), room=room_id)

    if room['players']['w'] is None and room['players']['b'] is None:
        ROOMS.pop(room_id, None)


HTML_PAYLOAD = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Wizard's Chess</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: #302e2b;
            color: #ffffff;
            overscroll-behavior: none;
            margin: 0; padding: 0;
        }

        .bg-panel { background-color: #262421; }
        .text-muted { color: #a7a6a2; }
        .sq-light { background-color: #ebecd0; }
        .sq-dark { background-color: #739552; }
        
        .sq-highlight {
            position: absolute; inset: 0;
            background-color: rgba(255, 255, 51, 0.4);
            pointer-events: none;
        }
        .sq-selected {
            position: absolute; inset: 0;
            background-color: rgba(20, 85, 30, 0.5);
            pointer-events: none;
        }
        .move-dot {
            width: 30%; height: 30%; border-radius: 50%;
            background-color: rgba(0, 0, 0, 0.2);
            position: absolute; pointer-events: none;
        }
        .capture-dot {
            width: 85%; height: 85%; border-radius: 50%;
            border: 6px solid rgba(0, 0, 0, 0.2);
            position: absolute; background: transparent; pointer-events: none;
        }

        .piece {
            width: 100%; height: 100%; background-size: contain;
            background-repeat: no-repeat; background-position: center;
            position: relative; z-index: 10; cursor: pointer;
            transition: transform 0.05s ease;
        }
        .piece:active { transform: scale(1.1); }

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
        ::-webkit-scrollbar-track { background: #1f1e1b; }
        ::-webkit-scrollbar-thumb { background: #3f3e3b; border-radius: 4px; }
        
        .spell-card { transition: all 0.2s; }
        .spell-card.active { border-color: #81b64c; box-shadow: 0 0 15px rgba(129, 182, 76, 0.4); transform: translateY(-4px); }
        .spell-card.used { opacity: 0.3; filter: grayscale(1); pointer-events: none; }
        
        .toast {
            position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
            background: #262421; border: 1px solid #81b64c; padding: 12px 24px;
            border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.8);
            z-index: 1000; display: none; font-weight: bold; text-align: center;
        }

        .overlay {
            position: absolute; inset: 0; background: rgba(0,0,0,0.6);
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            z-index: 50; backdrop-filter: blur(2px);
        }
    </style>
</head>
<body class="flex flex-col lg:flex-row h-screen overflow-hidden">

    <div id="toast" class="toast text-white">Message</div>

    <!-- Main Board Area -->
    <div class="flex-grow flex flex-col items-center justify-center p-2 lg:p-6 w-full lg:w-2/3 h-full overflow-y-auto">
        <div class="w-full max-w-[700px] flex flex-col gap-2">
            
            <!-- Top Player -->
            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-[#1f1e1b] rounded overflow-hidden flex items-center justify-center">
                        <img src="https://images.chesscomfiles.com/uploads/v1/user/default_dark.537554ee.png" class="w-full h-full object-cover">
                    </div>
                    <div>
                        <div class="font-bold text-sm" id="opp-name">Opponent</div>
                        <div class="text-xs text-muted" id="opp-status">Connecting...</div>
                        <div class="flex items-center mt-1" id="captured-top"></div>
                    </div>
                </div>
            </div>

            <!-- Board -->
            <div class="relative w-full aspect-square border-4 border-[#1f1e1b] rounded shadow-2xl overflow-hidden">
                <div id="board" class="w-full h-full grid grid-cols-8 grid-rows-8 select-none"></div>
                
                <!-- Waiting Overlay -->
                <div id="waiting-overlay" class="overlay">
                    <div class="bg-[#1f1e1b] border border-[#3f3e3b] p-6 rounded-lg text-center max-w-[80%]">
                        <h2 class="text-xl font-bold mb-2">Waiting for Opponent</h2>
                        <p class="text-sm text-muted mb-4">Share this room link with a friend to play.</p>
                        <input type="text" id="share-link" readonly class="w-full bg-[#141312] border border-[#3f3e3b] text-white p-2 rounded mb-2 text-xs font-mono">
                        <button onclick="copyLink()" class="bg-[#81b64c] text-black font-bold px-4 py-2 rounded text-sm w-full hover:bg-[#a3d160]">Copy Link</button>
                    </div>
                </div>

                <!-- Spell Banner -->
                <div id="spell-banner" class="hidden absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-purple-600 bg-opacity-95 text-white px-6 py-4 rounded-xl font-bold text-center z-50 shadow-2xl border border-purple-400 w-[80%] max-w-[300px]">
                    <div id="spell-banner-title" class="text-2xl mb-1">SPELL</div>
                    <div id="spell-banner-desc" class="text-sm font-normal text-purple-100 mb-4">Action</div>
                    <button onclick="cancelSpell()" class="text-sm bg-black bg-opacity-40 hover:bg-opacity-60 px-4 py-2 rounded w-full">Cancel Spell</button>
                </div>
            </div>

            <!-- Bottom Player -->
            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-[#1f1e1b] rounded overflow-hidden flex items-center justify-center">
                        <img src="https://images.chesscomfiles.com/uploads/v1/user/default_light.6456fef9.png" class="w-full h-full object-cover">
                    </div>
                    <div>
                        <div class="font-bold text-sm" id="my-name">You</div>
                        <div class="text-xs text-[#81b64c]" id="my-status">Connecting...</div>
                        <div class="flex items-center mt-1" id="captured-bottom"></div>
                    </div>
                </div>
            </div>

            <!-- Spells Hand -->
            <div class="mt-2 bg-panel border border-[#3f3e3b] p-3 rounded-lg shadow-lg">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="font-bold text-xs text-muted uppercase tracking-wider">Your Grimoire</h3>
                    <span id="turn-indicator" class="text-xs font-bold px-2 py-1 rounded bg-[#1f1e1b]"></span>
                </div>
                <div id="spells-container" class="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
                    <!-- Spells injected here -->
                </div>
            </div>

        </div>
    </div>

    <!-- Sidebar Area -->
    <div class="w-full lg:w-1/3 xl:w-[400px] bg-panel flex flex-col border-l border-[#3f3e3b] h-[30vh] lg:h-full">
        <!-- Move History -->
        <div class="p-3 border-b border-[#3f3e3b] font-bold text-sm text-muted uppercase">Match Log</div>
        <div class="flex-grow overflow-y-auto p-4 custom-scrollbar bg-[#1f1e1b]" id="move-history">
            <!-- Moves injected here -->
        </div>

        <!-- Rules -->
        <div class="p-4 bg-[#262421] border-t border-[#3f3e3b] text-xs text-muted leading-relaxed">
            <strong class="text-white">How to play:</strong> Tap to move. Spells bypass normal rules. Expelliarmus lets you keep your turn. Time-Turner rewinds the board.<br/>
            <span class="text-yellow-500">Legendary</span> | <span class="text-purple-400">Rare</span> | <span class="text-gray-400">Common</span>
        </div>
    </div>

<script>
    const socket = io();
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
        input.select(); document.execCommand('copy');
        showToast("Link Copied!");
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

    let selectedSquare = null;
    let activeSpell = null;
    let spellSourceSq = null;
    
    let moveLog = []; 
    let moveNum = 1;

    // --- DOM Board Building ---
    function buildBoardDOM() {
        const boardEl = document.getElementById('board');
        boardEl.innerHTML = '';
        const files = ['a','b','c','d','e','f','g','h'];
        const ranks = ['8','7','6','5','4','3','2','1'];
        
        const activeRanks = isFlipped ? [...ranks].reverse() : ranks;
        const activeFiles = isFlipped ? [...files].reverse() : files;

        for(let r=0; r<8; r++) {
            for(let f=0; f<8; f++) {
                const sqName = activeFiles[f] + activeRanks[r];
                const isLight = (r + f) % 2 === 0;
                
                const sqEl = document.createElement('div');
                sqEl.className = `relative flex items-center justify-center ${isLight ? 'sq-light' : 'sq-dark'}`;
                sqEl.id = `sq-${sqName}`;
                sqEl.onclick = () => handleSquareClick(sqName);
                
                const highlight = document.createElement('div');
                highlight.id = `hl-${sqName}`; highlight.style.display = 'none';
                
                const dot = document.createElement('div');
                dot.id = `dot-${sqName}`; dot.style.display = 'none';

                const piece = document.createElement('div');
                piece.id = `piece-${sqName}`; piece.className = 'piece'; piece.style.display = 'none';

                sqEl.appendChild(highlight);
                sqEl.appendChild(dot);
                sqEl.appendChild(piece);
                boardEl.appendChild(sqEl);
            }
        }
    }

    function showToast(msg) {
        const t = document.getElementById('toast');
        t.innerText = msg; t.style.display = 'block';
        setTimeout(() => t.style.display = 'none', 2500);
    }

    function isMyTurn() {
        return myColor && myColor !== 's' && gameReady && game.turn() === myColor;
    }

    function switchTurnInFen(fen) {
        let parts = fen.split(' ');
        parts[1] = parts[1] === 'w' ? 'b' : 'w';
        parts[3] = '-'; // clear en passant
        return parts.join(' ');
    }

    // --- User Interaction ---
    function handleSquareClick(sq) {
        if (!gameReady || myColor === 's' || !isMyTurn()) return;

        if (activeSpell) {
            processSpellClick(sq);
            return;
        }

        const p = game.get(sq);
        
        // Select own piece
        if (p && p.color === myColor) {
            selectedSquare = selectedSquare === sq ? null : sq;
            updateUI();
            return;
        }

        // Move
        if (selectedSquare) {
            const baseFen = game.fen();
            const move = game.move({ from: selectedSquare, to: sq, promotion: 'q' });
            if (move) {
                selectedSquare = null;
                updateUI();
                (move.captured ? sfxCapture : sfxMove).play().catch(()=>{});
                appendLog(move.san, myColor);
                socket.emit('standard_move', { room, base_fen: baseFen, from: move.from, to: move.to, san: move.san, color: move.color, fen: game.fen() });
            } else {
                selectedSquare = null;
                updateUI();
            }
        }
    }

    function processSpellClick(sq) {
        const p = game.get(sq);
        const opp = myColor === 'w' ? 'b' : 'w';
        const baseFen = game.fen();
        let nextFen = null;

        switch(activeSpell.type) {
            case 'enemy':
                if (p && p.color === opp && p.type !== 'k') {
                    game.remove(sq);
                    if (activeSpell.id === 'sectum') game.put({type: 'p', color: opp}, sq);
                    nextFen = switchTurnInFen(game.fen());
                    commitSpellEffect(activeSpell, baseFen, nextFen, true);
                } else showToast("Select a valid enemy piece.");
                break;
                
            case 'any':
                const fileIdx = sq.charCodeAt(0);
                const rankIdx = parseInt(sq[1]);
                for(let f = fileIdx-1; f <= fileIdx+1; f++) {
                    for(let r = rankIdx-1; r <= rankIdx+1; r++) {
                        const targetSq = String.fromCharCode(f) + r;
                        const tP = game.get(targetSq);
                        if (tP && tP.type !== 'k') game.remove(targetSq);
                    }
                }
                nextFen = switchTurnInFen(game.fen());
                commitSpellEffect(activeSpell, baseFen, nextFen, true);
                break;

            case 'own_pawn':
                if (p && p.color === myColor && p.type === 'p') {
                    game.remove(sq);
                    game.put({type: 'n', color: myColor}, sq);
                    nextFen = switchTurnInFen(game.fen());
                    commitSpellEffect(activeSpell, baseFen, nextFen, true);
                } else showToast("Select your own Pawn.");
                break;

            case 'drag_own':
            case 'drag_enemy':
                if (!spellSourceSq) {
                    const reqColor = activeSpell.type === 'drag_own' ? myColor : opp;
                    if (p && p.color === reqColor) {
                        spellSourceSq = sq;
                        updateUI();
                    } else showToast("Select a valid piece.");
                } else {
                    const source = spellSourceSq;
                    const fDist = Math.abs(source.charCodeAt(0) - sq.charCodeAt(0));
                    const rDist = Math.abs(parseInt(source[1]) - parseInt(sq[1]));
                    
                    if (activeSpell.id === 'accio' && (fDist > 2 || rDist > 2)) return showToast("Too far (max 2 sq).");
                    if (activeSpell.id === 'leviosa' && ((fDist > 1 || rDist > 1) || p)) return showToast("Must be adjacent empty square.");
                    if (activeSpell.id === 'alohomora') {
                        const isOwnHalf = myColor === 'w' ? parseInt(sq[1]) <= 4 : parseInt(sq[1]) >= 5;
                        if (!isOwnHalf || p) return showToast("Must be empty square on your half.");
                    }
                    
                    if (activeSpell.id === 'imperio') {
                        game.load(switchTurnInFen(game.fen()));
                        const move = game.move({from: source, to: sq, promotion:'q'});
                        if (move) {
                            nextFen = game.fen(); // move() already swapped turn back to myColor, so we need to swap it again to give turn to opp
                            nextFen = switchTurnInFen(nextFen); 
                            commitSpellEffect(activeSpell, baseFen, nextFen, true, `IMPERIO: ${move.san}`);
                        } else {
                            game.load(baseFen); 
                            showToast("Illegal move for that piece.");
                            spellSourceSq = null; updateUI();
                        }
                        return;
                    }

                    // Accio, Leviosa, Alohomora:
                    const movePiece = game.get(source);
                    game.remove(source);
                    game.put(movePiece, sq);
                    nextFen = switchTurnInFen(game.fen());
                    commitSpellEffect(activeSpell, baseFen, nextFen, true);
                }
                break;
        }
    }

    function processInstantSpell(spell) {
        const baseFen = game.fen();
        if (spell.id === 'time') {
            commitSpellEffect(spell, baseFen, null, true); // Backend handles rewind fen
        }
        if (spell.id === 'expelliarmus') {
            commitSpellEffect(spell, baseFen, baseFen, false); // Turn not consumed
        }
    }

    function commitSpellEffect(spell, baseFen, newFen, consumeTurn, customLog = null) {
        usedSpells.add(spell.id);
        const logStr = customLog || spell.name.toUpperCase();
        
        socket.emit('spell_effect', { 
            room, base_fen: baseFen, spell_id: spell.id, name: spell.name, 
            fen: newFen, consume_turn: consumeTurn, log: logStr 
        });

        // Optimistic UI Update
        if (newFen) game.load(newFen);
        sfxSpell.play().catch(()=>{});
        appendLog(logStr, myColor, true);
        cancelSpell();
    }

    function cancelSpell() {
        activeSpell = null; spellSourceSq = null; selectedSquare = null;
        document.getElementById('spell-banner').classList.add('hidden');
        updateUI();
    }

    // --- Logging & UI ---
    function appendLog(text, color, isSpell = false) {
        const style = isSpell ? 'text-purple-400 font-bold' : '';
        if (color === 'w') {
            $('#move-history').append(`<div class="flex py-1 border-b border-[#3f3e3b]"><div class="w-8 text-muted">${moveNum}.</div><div class="w-1/2 ${style}">${text}</div><div class="w-1/2" id="black-move-${moveNum}"></div></div>`);
        } else {
            const el = document.getElementById(`black-move-${moveNum}`);
            if (el) el.innerHTML = `<span class="${style}">${text}</span>`;
            else $('#move-history').append(`<div class="flex py-1 border-b border-[#3f3e3b]"><div class="w-8 text-muted">${moveNum}.</div><div class="w-1/2"></div><div class="w-1/2 ${style}">${text}</div></div>`);
            moveNum++;
        }
        const hist = document.getElementById('move-history');
        hist.scrollTop = hist.scrollHeight;
    }

    function updateUI() {
        const turn = game.turn();
        
        // 1. Board Status
        const files = ['a','b','c','d','e','f','g','h'];
        const ranks = ['8','7','6','5','4','3','2','1'];
        let legalMoves = selectedSquare ? game.moves({ square: selectedSquare, verbose: true }) : [];

        for(let r of ranks) {
            for(let f of files) {
                const sq = f + r;
                const p = game.get(sq);
                
                const pieceEl = document.getElementById(`piece-${sq}`);
                const hlEl = document.getElementById(`hl-${sq}`);
                const dotEl = document.getElementById(`dot-${sq}`);
                
                if (p) {
                    pieceEl.className = `piece ${p.color}${p.type.toUpperCase()}`;
                    pieceEl.style.display = 'block';
                } else {
                    pieceEl.style.display = 'none';
                    pieceEl.className = 'piece';
                }

                hlEl.className = 'sq-highlight'; hlEl.style.display = 'none';
                dotEl.style.display = 'none';

                if (sq === selectedSquare || sq === spellSourceSq) {
                    hlEl.className = 'sq-selected'; hlEl.style.display = 'block';
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

        // 2. Turn Indicators
        const isMy = turn === myColor;
        document.getElementById('turn-indicator').innerText = isMy ? "YOUR TURN" : "OPPONENT'S TURN";
        document.getElementById('turn-indicator').className = `text-[10px] font-bold px-2 py-1 rounded ${isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
        
        document.getElementById('my-status').innerText = isMy ? 'Thinking...' : 'Waiting...';
        document.getElementById('opp-status').innerText = !isMy ? 'Thinking...' : 'Waiting...';
        document.getElementById('my-status').className = `text-xs ${isMy ? 'text-[#81b64c]' : 'text-muted'}`;
        document.getElementById('opp-status').className = `text-xs ${!isMy ? 'text-[#81b64c]' : 'text-muted'}`;

        // 3. Spells
        const handContainer = document.getElementById('spells-container');
        handContainer.innerHTML = '';
        
        if (myHand && myColor !== 's') {
            myHand.forEach(spell => {
                const isUsed = usedSpells.has(spell.id);
                const isActive = activeSpell && activeSpell.id === spell.id;
                
                let borderClass = 'border-[#3f3e3b]';
                if (spell.rarity === 'Legendary') borderClass = 'border-b-4 border-yellow-500';
                if (spell.rarity === 'Rare') borderClass = 'border-b-4 border-purple-500';
                if (spell.rarity === 'Common') borderClass = 'border-b-4 border-gray-400';

                const card = document.createElement('div');
                card.className = `spell-card flex-shrink-0 w-[100px] p-2 rounded-lg bg-[#1f1e1b] border ${borderClass} ${!isUsed && isMyTurn() ? 'cursor-pointer' : ''} flex flex-col items-center text-center ${isUsed ? 'used' : ''} ${isActive ? 'active' : ''}`;
                
                card.innerHTML = `
                    <div class="text-2xl mb-1">${spell.icon}</div>
                    <div class="text-[10px] font-bold leading-tight mb-1">${spell.name}</div>
                    <div class="text-[9px] text-muted leading-tight">${spell.desc}</div>
                `;
                
                card.onclick = () => {
                    if (isUsed || !isMyTurn()) return;
                    if (isActive) { cancelSpell(); return; }
                    
                    if (spell.type === 'instant') {
                        processInstantSpell(spell);
                    } else {
                        selectedSquare = null; activeSpell = spell; spellSourceSq = null;
                        const banner = document.getElementById('spell-banner');
                        document.getElementById('spell-banner-title').innerText = `${spell.icon} ${spell.name}`;
                        document.getElementById('spell-banner-desc').innerText = spell.desc;
                        banner.classList.remove('hidden');
                        updateUI();
                    }
                };
                handContainer.appendChild(card);
            });
        }

        calcMaterial();
    }

    function calcMaterial() {
        const counts = { w: {p:0,n:0,b:0,r:0,q:0}, b: {p:0,n:0,b:0,r:0,q:0} };
        for (let r=0; r<8; r++) {
            for(let f=0; f<8; f++) {
                const p = game.get(String.fromCharCode(97+f)+(r+1));
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
            for(let i=0; i<bMiss; i++) { capW += `<div class="mini-piece b${type.toUpperCase()}"></div>`; wScore += values[type]; }
            for(let i=0; i<wMiss; i++) { capB += `<div class="mini-piece w${type.toUpperCase()}"></div>`; bScore += values[type]; }
        });

        const bottomAdv = wScore > bScore ? (myColor==='w'?wScore-bScore:'') : (bScore>wScore ? (myColor==='b'?bScore-wScore:'') : '');
        const topAdv = wScore > bScore ? (myColor==='b'?wScore-bScore:'') : (bScore>wScore ? (myColor==='w'?bScore-wScore:'') : '');

        document.getElementById('captured-bottom').innerHTML = (myColor==='w' ? capW : capB) + (bottomAdv ? `<span class="text-xs text-muted ml-1 font-bold">+${bottomAdv}</span>` : '');
        document.getElementById('captured-top').innerHTML = (myColor==='w' ? capB : capW) + (topAdv ? `<span class="text-xs text-muted ml-1 font-bold">+${topAdv}</span>` : '');
    }

    // --- Socket Listeners ---
    socket.on('connect', () => {
        socket.emit('join_room', { room });
    });

    socket.on('role_assigned', (data) => {
        myColor = data.color;
        myHand = data.hand;
        usedSpells = new Set();
        isFlipped = myColor === 'b';
        
        if (myColor === 'w') { document.getElementById('my-name').innerText = 'You (White)'; document.getElementById('opp-name').innerText = 'Opponent (Black)'; }
        else if (myColor === 'b') { document.getElementById('my-name').innerText = 'You (Black)'; document.getElementById('opp-name').innerText = 'Opponent (White)'; }
        else { document.getElementById('my-name').innerText = 'Spectator'; document.getElementById('opp-name').innerText = 'Players'; }

        buildBoardDOM();
        game.load(data.snapshot.fen);
        updateUI();
    });

    socket.on('room_state', (state) => {
        if (state.started) {
            document.getElementById('waiting-overlay').style.display = 'none';
            gameReady = true;
        } else {
            document.getElementById('waiting-overlay').style.display = 'flex';
            gameReady = false;
        }
    });

    socket.on('game_ready', (state) => {
        document.getElementById('waiting-overlay').style.display = 'none';
        gameReady = true;
        sfxStart.play().catch(()=>{});
        showToast("Match Started!");
        updateUI();
    });

    socket.on('standard_move', (data) => {
        game.load(data.fen);
        (data.san.includes('x') ? sfxCapture : sfxMove).play().catch(()=>{});
        appendLog(data.san, data.color);
        updateUI();
    });

    socket.on('spell_effect', (data) => {
        if (data.fen) game.load(data.fen);
        sfxSpell.play().catch(()=>{});
        appendLog(data.log || data.name, data.color, true);
        if (data.color === myColor) usedSpells.add(data.spell_id);
        cancelSpell();
    });

    socket.on('action_denied', (data) => {
        showToast(data.reason);
        if (data.snapshot && data.snapshot.fen) {
            game.load(data.snapshot.fen);
        }
        cancelSpell();
    });

</script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'> SERVER ONLINE. PORT: {port}')
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
