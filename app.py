import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'wizard_chess_secret_vfinal')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

# 100% FontAwesome Icons - No Emojis
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

ROOMS = {}

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
            'player_ids': {'w': None, 'b': None}, # Uses localStorage UUIDs (Persistent)
            'hands': {'w': None, 'b': None},
            'used': {'w': set(), 'b': set()}
        }
    return ROOMS[room_id]

def snapshot(room_id: str):
    room = ROOMS.get(room_id)
    if not room: return {}
    return {
        'room': room_id,
        'fen': room['fen'],
        'turn': room['turn'],
        'started': room['player_ids']['w'] is not None and room['player_ids']['b'] is not None,
    }

@app.route('/')
def index():
    return render_template_string(HTML_PAYLOAD)

@socketio.on('join_room')
def handle_join(data):
    room_id = data.get('room')
    player_id = data.get('player_id') 
    if not room_id or not player_id: return

    room = get_room(room_id)

    # Bulletproof persistent role assignment
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

    if color in ('w', 'b'):
        if room['hands'][color] is None:
            room['hands'][color] = fresh_hand()

    # Inform the connecting user of their state
    emit('role_assigned', {
        'color': color,
        'hand': room['hands'].get(color, []) if color in ('w', 'b') else [],
        'snapshot': snapshot(room_id),
    }, to=request.sid)

    # Inform the whole room of the current state
    emit('room_state', snapshot(room_id), to=room_id)

@socketio.on('standard_move')
def handle_standard_move(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    if not room_id or room_id not in ROOMS: return

    room = ROOMS[room_id]
    color = 'w' if room['player_ids']['w'] == player_id else ('b' if room['player_ids']['b'] == player_id else None)
    
    if not color or room['turn'] != color: return

    new_fen = data.get('fen')
    room['fen'] = new_fen
    room['turn'] = fen_side_to_move(new_fen)
    room['history'].append(new_fen)

    emit('board_update', {
        'fen': room['fen'],
        'san': data.get('san'),
        'color': color,
        'turn': room['turn'],
        'is_spell': False
    }, to=room_id)

@socketio.on('spell_effect')
def handle_spell_effect(data):
    room_id = data.get('room')
    player_id = data.get('player_id')
    if not room_id or room_id not in ROOMS: return

    room = ROOMS[room_id]
    color = 'w' if room['player_ids']['w'] == player_id else ('b' if room['player_ids']['b'] == player_id else None)
    
    if not color or room['turn'] != color: return

    spell_id = data.get('spell_id')
    if spell_id in room['used'][color]: return

    consume_turn = bool(data.get('consume_turn', True))
    new_fen = data.get('fen')

    if spell_id == 'time':
        if len(room['history']) < 2: return
        room['history'].pop() 
        new_fen = room['history'][-1]
        consume_turn = True

    if spell_id == 'expelliarmus':
        consume_turn = False
        new_fen = room['fen']

    room['used'][color].add(spell_id)
    room['fen'] = new_fen
    if consume_turn:
        room['turn'] = fen_side_to_move(new_fen)
    
    if spell_id != 'time':
        room['history'].append(new_fen)

    emit('board_update', {
        'fen': room['fen'],
        'spell_id': spell_id,
        'san': data.get('log', ''),
        'color': color,
        'turn': room['turn'],
        'is_spell': True,
        'used_spell_id': spell_id
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: #302e2b;
            color: #ffffff;
            overscroll-behavior: none;
            margin: 0; padding: 0;
            overflow: hidden; 
        }

        .bg-panel { background-color: #262421; }
        .text-muted { color: #a7a6a2; }
        
        /* Exact Chess.com Board Colors */
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
            width: 32%; height: 32%; border-radius: 50%;
            background-color: rgba(0, 0, 0, 0.25);
            position: absolute; pointer-events: none;
        }
        .capture-dot {
            width: 85%; height: 85%; border-radius: 50%;
            border: 6px solid rgba(0, 0, 0, 0.25);
            position: absolute; background: transparent; pointer-events: none;
        }

        .piece {
            width: 100%; height: 100%; background-size: contain;
            background-repeat: no-repeat; background-position: center;
            position: relative; z-index: 10; cursor: pointer;
            transition: transform 0.05s ease;
            user-select: none; 
            -webkit-user-drag: none; /* CRITICAL FIX: Stops laptop image dragging bug */
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
        ::-webkit-scrollbar-track { background: #262421; }
        ::-webkit-scrollbar-thumb { background: #4b4845; border-radius: 4px; }
        
        .spell-card { transition: all 0.2s; position: relative; overflow: hidden; }
        .spell-card::before { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, transparent 100%); pointer-events: none; }
        .spell-card.active { border-color: #81b64c; box-shadow: 0 0 15px rgba(129, 182, 76, 0.4); transform: translateY(-4px); }
        .spell-card.used { opacity: 0.25; filter: grayscale(1); pointer-events: none; }
        
        .overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.7); display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 50; backdrop-filter: blur(4px); }
        
        /* Tight Full-Screen Chess Layout */
        .board-wrapper { width: 100%; height: 100%; max-width: 85vh; display: flex; flex-direction: column; justify-content: center; margin: 0 auto; }
    </style>
</head>
<body class="flex flex-col lg:flex-row h-screen">

    <!-- MAIN BOARD AREA -->
    <div class="flex-grow flex flex-col justify-center p-2 lg:p-4 bg-[#302e2b] overflow-hidden">
        <div class="board-wrapper gap-1.5 lg:gap-3 relative">
            
            <!-- Top Player (Opponent) -->
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

            <!-- Chess Board -->
            <div class="w-full aspect-square rounded shadow-2xl overflow-hidden relative border-4 border-[#262421]">
                <div id="board" class="w-full h-full grid grid-cols-8 grid-rows-8 select-none bg-[#739552]"></div>
                
                <!-- Waiting Overlay -->
                <div id="waiting-overlay" class="overlay">
                    <div class="bg-[#262421] border border-[#3f3e3b] p-6 rounded-xl text-center max-w-[85%] shadow-2xl">
                        <h2 class="text-xl font-bold mb-2 text-white"><i class="fa-solid fa-chess-knight text-[#81b64c] mr-2"></i>Match Lobby</h2>
                        <p class="text-sm text-muted mb-4">Send this link to a friend to start the match.</p>
                        <div class="flex gap-2">
                            <input type="text" id="share-link" readonly class="w-full bg-[#141312] border border-[#3f3e3b] text-white p-3 rounded-lg text-xs font-mono focus:outline-none">
                            <button onclick="copyLink()" class="bg-[#81b64c] hover:bg-[#a3d160] text-black font-extrabold px-4 rounded-lg text-sm transition"><i class="fa-solid fa-copy"></i></button>
                        </div>
                    </div>
                </div>

                <!-- Spell Guidance Overlay -->
                <div id="spell-banner" class="hidden absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-purple-700 to-purple-500 text-white px-6 py-4 rounded-xl font-bold text-center z-50 shadow-[0_0_30px_rgba(168,85,247,0.5)] border border-purple-300 w-[85%] max-w-[320px]">
                    <div id="spell-banner-title" class="text-xl mb-1 drop-shadow-md">SPELL</div>
                    <div id="spell-banner-desc" class="text-sm font-medium text-purple-100 mb-4">Action</div>
                    <button onclick="cancelSpell()" class="text-sm bg-black bg-opacity-40 hover:bg-opacity-60 px-4 py-2 rounded-lg w-full transition uppercase tracking-wider font-bold">Cancel</button>
                </div>
            </div>

            <!-- Bottom Player (You) -->
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

    <!-- SIDEBAR AREA -->
    <div class="w-full lg:w-[380px] xl:w-[420px] bg-[#262421] border-l border-[#3f3e3b] flex flex-col h-[35vh] lg:h-full z-10 shadow-2xl flex-shrink-0">
        
        <!-- Spell Grimoire -->
        <div class="p-4 border-b border-[#3f3e3b] bg-[#211f1c]">
            <div class="flex justify-between items-center mb-3">
                <h3 class="font-bold text-xs text-muted uppercase tracking-widest"><i class="fa-solid fa-book-journal-whills mr-2"></i>Your Grimoire</h3>
                <span id="turn-indicator" class="text-[10px] font-bold px-2 py-1 rounded bg-[#1f1e1b] text-muted">WAITING</span>
            </div>
            <div id="spells-container" class="flex lg:grid lg:grid-cols-3 gap-2 overflow-x-auto lg:overflow-y-auto lg:max-h-[220px] custom-scrollbar pb-2 lg:pb-0 pr-1">
                <!-- Spells injected here -->
            </div>
        </div>

        <!-- Match History -->
        <div class="px-4 py-3 border-b border-[#3f3e3b] flex justify-between items-center bg-[#262421]">
            <span class="font-bold text-xs text-muted uppercase tracking-widest"><i class="fa-solid fa-list-ul mr-2"></i>Match Log</span>
            <button onclick="window.location.href='/';" class="text-xs text-red-400 hover:text-red-300 transition font-bold"><i class="fa-solid fa-flag mr-1"></i>Resign</button>
        </div>
        <div class="flex-grow overflow-y-auto p-4 custom-scrollbar bg-[#1f1e1b] font-mono text-sm shadow-inner" id="move-history">
            <!-- Moves injected here -->
        </div>
    </div>

<script>
    const socket = io();
    
    // CRITICAL FIX: Bulletproof Persistent ID. If you refresh, close tab, or sleep phone, you stay you.
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
        document.getElementById('share-link').select(); 
        document.execCommand('copy');
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
    let moveNum = 1;

    // DOM Grid Creation (Zero Flickering)
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

    function isMyTurn() {
        return myColor && myColor !== 's' && gameReady && game.turn() === myColor;
    }

    function switchTurnInFen(fen) {
        let parts = fen.split(' ');
        parts[1] = parts[1] === 'w' ? 'b' : 'w';
        parts[3] = '-'; 
        return parts.join(' ');
    }

    // Interactive Tap-to-Move
    function handleSquareClick(sq) {
        if (!gameReady || myColor === 's' || !isMyTurn()) return;

        if (activeSpell) {
            processSpellClick(sq);
            return;
        }

        const p = game.get(sq);
        
        // 1. Select
        if (p && p.color === myColor) {
            selectedSquare = selectedSquare === sq ? null : sq;
            updateUI();
            return;
        }

        // 2. Move
        if (selectedSquare) {
            const baseFen = game.fen();
            const move = game.move({ from: selectedSquare, to: sq, promotion: 'q' });
            if (move) {
                selectedSquare = null;
                updateUI();
                socket.emit('standard_move', { 
                    room, player_id: playerId, base_fen: baseFen, 
                    from: move.from, to: move.to, san: move.san, fen: game.fen() 
                });
            } else {
                selectedSquare = null;
                updateUI();
            }
        }
    }

    // Spell Execution Logic (Overrides Engine)
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
                }
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
                }
                break;

            case 'drag_own':
            case 'drag_enemy':
                if (!spellSourceSq) {
                    const reqColor = activeSpell.type === 'drag_own' ? myColor : opp;
                    if (p && p.color === reqColor) {
                        spellSourceSq = sq;
                        updateUI();
                    }
                } else {
                    const source = spellSourceSq;
                    const fDist = Math.abs(source.charCodeAt(0) - sq.charCodeAt(0));
                    const rDist = Math.abs(parseInt(source[1]) - parseInt(sq[1]));
                    
                    if (activeSpell.id === 'accio' && (fDist > 2 || rDist > 2)) return;
                    if (activeSpell.id === 'leviosa' && ((fDist > 1 || rDist > 1) || p)) return;
                    if (activeSpell.id === 'alohomora') {
                        const isOwnHalf = myColor === 'w' ? parseInt(sq[1]) <= 4 : parseInt(sq[1]) >= 5;
                        if (!isOwnHalf || p) return;
                    }
                    
                    if (activeSpell.id === 'imperio') {
                        game.load(switchTurnInFen(game.fen()));
                        const move = game.move({from: source, to: sq, promotion:'q'});
                        if (move) {
                            nextFen = switchTurnInFen(game.fen()); 
                            commitSpellEffect(activeSpell, baseFen, nextFen, true, `IMPERIO: ${move.san}`);
                        } else {
                            game.load(baseFen); 
                            spellSourceSq = null; updateUI();
                        }
                        return;
                    }

                    const movePiece = game.get(source);
                    game.remove(source);
                    game.put(movePiece, sq);
                    nextFen = switchTurnInFen(game.fen());
                    commitSpellEffect(activeSpell, baseFen, nextFen, true);
                }
                break;
        }
    }

    function commitSpellEffect(spell, baseFen, newFen, consumeTurn, customLog = null) {
        usedSpells.add(spell.id);
        socket.emit('spell_effect', { 
            room, player_id: playerId, base_fen: baseFen, 
            spell_id: spell.id, name: spell.name, fen: newFen, 
            consume_turn: consumeTurn, log: customLog || spell.name.toUpperCase() 
        });
        cancelSpell();
    }

    function cancelSpell() {
        activeSpell = null; spellSourceSq = null; selectedSquare = null;
        document.getElementById('spell-banner').classList.add('hidden');
        updateUI();
    }

    function appendLog(text, color, isSpell = false) {
        const style = isSpell ? 'text-purple-400 font-bold' : 'text-[#e3e3e3]';
        const icon = isSpell ? '<i class="fa-solid fa-wand-magic-sparkles text-[10px] mr-1 text-purple-400"></i>' : '';
        
        if (color === 'w') {
            $('#move-history').append(`<div class="flex py-1.5 border-b border-[#3f3e3b]"><div class="w-8 text-muted">${moveNum}.</div><div class="w-1/2 ${style}">${icon}${text}</div><div class="w-1/2 text-right text-muted" id="black-move-${moveNum}">...</div></div>`);
        } else {
            const el = document.getElementById(`black-move-${moveNum}`);
            if (el) {
                el.innerHTML = `<span class="${style}">${icon}${text}</span>`;
                el.classList.remove('text-muted');
                el.classList.add('text-left'); 
            } else {
                $('#move-history').append(`<div class="flex py-1.5 border-b border-[#3f3e3b]"><div class="w-8 text-muted">${moveNum}.</div><div class="w-1/2"></div><div class="w-1/2 ${style}">${icon}${text}</div></div>`);
            }
            moveNum++;
        }
        const hist = document.getElementById('move-history');
        hist.scrollTop = hist.scrollHeight;
    }

    function updateUI() {
        const turn = game.turn();
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

        const isMy = turn === myColor;
        const myStatus = document.getElementById('my-status');
        const oppStatus = document.getElementById('opp-status');
        const turnIndicator = document.getElementById('turn-indicator');

        if (gameReady) {
            turnIndicator.innerText = isMy ? "YOUR TURN" : "OPPONENT'S TURN";
            turnIndicator.className = `text-[10px] font-bold px-2 py-1 rounded shadow ${isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
            myStatus.innerText = isMy ? "Thinking" : "Waiting";
            myStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow ${isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
            oppStatus.innerText = !isMy ? "Thinking" : "Waiting";
            oppStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow ${!isMy ? 'bg-[#81b64c] text-black' : 'bg-[#1f1e1b] text-muted'}`;
        }

        const handContainer = document.getElementById('spells-container');
        handContainer.innerHTML = '';
        
        if (myHand && myColor !== 's') {
            myHand.forEach(spell => {
                const isUsed = usedSpells.has(spell.id);
                const isActive = activeSpell && activeSpell.id === spell.id;
                
                let borderClass = 'border-[#3f3e3b] text-gray-400';
                if (spell.rarity === 'Legendary') borderClass = 'border-b-4 border-yellow-500 text-yellow-400';
                if (spell.rarity === 'Rare') borderClass = 'border-b-4 border-purple-500 text-purple-400';

                const card = document.createElement('div');
                card.className = `spell-card min-w-[100px] lg:w-auto p-3 rounded-xl bg-[#1a1917] border ${borderClass} ${!isUsed && isMyTurn() ? 'cursor-pointer hover:bg-[#201e1c]' : ''} flex flex-col items-center justify-center text-center ${isUsed ? 'used' : ''} ${isActive ? 'active' : ''} shadow-lg`;
                
                card.innerHTML = `
                    <div class="text-2xl mb-1 drop-shadow-md"><i class="${spell.icon}"></i></div>
                    <div class="text-[10px] font-extrabold leading-tight mb-1 text-white tracking-wide">${spell.name}</div>
                    <div class="text-[9px] text-muted leading-tight hidden lg:block">${spell.desc}</div>
                `;
                
                card.onclick = () => {
                    if (isUsed || !isMyTurn()) return;
                    if (isActive) { cancelSpell(); return; }
                    
                    if (spell.type === 'instant') {
                        const baseFen = game.fen();
                        usedSpells.add(spell.id);
                        socket.emit('spell_effect', { room, player_id: playerId, base_fen: baseFen, spell_id: spell.id, name: spell.name, fen: baseFen, consume_turn: false, log: spell.name.toUpperCase() });
                    } else {
                        selectedSquare = null; activeSpell = spell; spellSourceSq = null;
                        const banner = document.getElementById('spell-banner');
                        document.getElementById('spell-banner-title').innerHTML = `<i class="${spell.icon} mr-2"></i>${spell.name}`;
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

    // --- Core Server Communication ---
    socket.on('connect', () => {
        socket.emit('join_room', { room, player_id: playerId });
    });

    socket.on('role_assigned', (data) => {
        myColor = data.color;
        myHand = data.hand;
        usedSpells = new Set();
        isFlipped = myColor === 'b';
        
        if (myColor === 'w') { 
            document.getElementById('my-name').innerText = 'You (White)'; 
            document.getElementById('my-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png';
            document.getElementById('opp-name').innerText = 'Opponent (Black)'; 
            document.getElementById('opp-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png';
        } else if (myColor === 'b') { 
            document.getElementById('my-name').innerText = 'You (Black)'; 
            document.getElementById('my-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png';
            document.getElementById('opp-name').innerText = 'Opponent (White)'; 
            document.getElementById('opp-avatar').src = 'https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png';
        }

        buildBoardDOM();
        game.load(data.snapshot.fen);
        updateUI();
    });

    socket.on('room_state', (state) => {
        if (state.started) {
            document.getElementById('waiting-overlay').style.display = 'none';
            if (!gameReady) sfxStart.play().catch(()=>{});
            gameReady = true;
        }
        updateUI();
    });

    socket.on('board_update', (data) => {
        game.load(data.fen);
        if (data.is_spell) {
            sfxSpell.play().catch(()=>{});
            if (data.color === myColor) usedSpells.add(data.used_spell_id);
        } else {
            (data.san.includes('x') ? sfxCapture : sfxMove).play().catch(()=>{});
        }
        appendLog(data.san, data.color, data.is_spell);
        updateUI();
    });

</script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'> SERVER ONLINE. PORT: {port}')
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
