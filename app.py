import os
from flask import Flask
from flask_socketio import SocketIO, join_room, emit
from flask import request

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lumos_maxima_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

client_rooms = {}
room_counts = {}

def keep_proper_logs(room_id, action):
    print(f"[ROOM: {room_id}] {action}")

@app.route('/')
def index():
    return HTML_PAYLOAD

@socketio.on('join_room')
def handle_join(room_id):
    join_room(room_id)
    client_rooms[request.sid] = room_id
    
    if room_id not in room_counts:
        room_counts[room_id] = 0
    room_counts[room_id] += 1
    
    color = 'w' if room_counts[room_id] == 1 else 'b'
    emit('role_assigned', color)
    
    keep_proper_logs(room_id, f"User connected. Assigned role: {'White' if color == 'w' else 'Black'}")
    
    if room_counts[room_id] >= 2:
        emit('user_joined', room=room_id)

@socketio.on('standard_move')
def handle_standard_move(move_data):
    room_id = client_rooms.get(request.sid)
    keep_proper_logs(room_id, f"Standard move: {move_data['from']} to {move_data['to']}")
    emit('standard_move', move_data, room=room_id, include_self=False)

@socketio.on('magic_sync')
def handle_magic_sync(fen_state):
    room_id = client_rooms.get(request.sid)
    keep_proper_logs(room_id, f"Magical Board Alteration synced.")
    emit('magic_sync', fen_state, room=room_id, include_self=False)

@socketio.on('spell_cast')
def handle_spell_cast(spell_data):
    room_id = client_rooms.get(request.sid)
    keep_proper_logs(room_id, f"Spell Cast: {spell_data['name']}")
    emit('spell_cast', spell_data, room=room_id, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    room_id = client_rooms.get(request.sid)
    if room_id:
        room_counts[room_id] -= 1
        keep_proper_logs(room_id, 'User disconnected.')
        del client_rooms[request.sid]

# ========================================================
# TRUE CHESS.COM INSPIRED UI WITH CAPTURED PIECES & SPELLS
# ========================================================
HTML_PAYLOAD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wizard's Chess</title>
    
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
    
    <style>
        :root {
            --bg-main: #312e2b;
            --bg-sidebar: #262421;
            --bg-panel: #21201d;
            --bg-hover: #3c3a38;
            --text-main: #fff;
            --text-muted: #989795;
            --accent-green: #81b64c;
            --accent-green-hover: #a3d160;
            --border-color: #403d39;
            --gold: #f1b24a;
            --purple: #a855f7;
            --silver: #a7a6a2;
            --magic-glow: rgba(168, 85, 247, 0.6);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }

        #header-bar {
            width: 100%;
            background: #21201d;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-sizing: border-box;
            border-bottom: 5px solid #1a1917;
        }
        
        .header-logo {
            font-weight: 800;
            font-size: 1.3rem;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .info-btn {
            background: #444; color: #fff; border-radius: 50%; width: 32px; height: 32px;
            display: flex; align-items: center; justify-content: center; font-weight: bold;
            cursor: pointer; border: none; font-size: 1.1rem; transition: 0.2s;
        }
        .info-btn:hover { background: #666; }

        .main-container {
            display: flex;
            justify-content: center;
            align-items: flex-start;
            gap: 20px;
            margin-top: 20px;
            margin-bottom: 40px;
            width: 100%;
            max-width: 1100px;
            flex-wrap: wrap;
        }

        .board-wrapper {
            display: flex;
            flex-direction: column;
            width: 550px;
        }

        /* Player Tags, Timers & Captured Pieces */
        .player-tag {
            display: flex; flex-direction: column; justify-content: center;
            padding: 10px 0; min-height: 50px;
        }
        .player-info {
            display: flex; align-items: center; justify-content: space-between; font-weight: bold; font-size: 1rem;
        }
        
        .user-block { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 32px; height: 32px; background: #555; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
        
        /* The Clocks */
        .clock {
            background: rgba(0,0,0,0.5); color: #fff; padding: 6px 12px; border-radius: 4px;
            font-family: monospace; font-size: 1.2rem; font-weight: bold; border: 1px solid var(--border-color);
        }
        .clock.active { background: #fff; color: #000; border-color: #fff;}

        .captured-area { display: flex; align-items: center; height: 25px; margin-top: 4px; padding-left: 42px; }
        .captured-piece { width: 22px; height: 22px; background-size: cover; margin-right: -8px; }
        .material-adv { margin-left: 15px; font-size: 0.85rem; font-weight: bold; color: var(--text-muted); }

        /* The Board */
        .board-core {
            border-radius: 4px; box-shadow: 0 4px 15px rgba(0,0,0,0.4); transition: 0.3s;
            border: 2px solid transparent;
        }
        .board-core.magic-active {
            box-shadow: 0 0 40px var(--magic-glow); border: 2px solid var(--purple); cursor: crosshair;
        }
        #board { width: 100%; }

        /* Spell Instruction Bar */
        #spell-instruction {
            background: var(--purple); color: #fff; font-weight: bold; padding: 10px;
            text-align: center; border-radius: 4px; margin-top: 10px; display: none;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }

        /* Deck & Spells */
        .deck-container {
            margin-top: 15px;
            background: var(--bg-sidebar);
            padding: 15px;
            border-radius: 6px;
        }
        .deck-title {
            font-size: 0.85rem; text-transform: uppercase; color: var(--text-muted); font-weight: 800; margin-bottom: 10px;
        }
        .spells-row {
            display: flex; gap: 10px; overflow-x: auto; padding-bottom: 5px;
        }
        
        .spell-card {
            min-width: 90px; width: 90px; height: 120px;
            background: var(--bg-main); border: 2px solid var(--border-color);
            border-radius: 6px; display: flex; flex-direction: column; align-items: center;
            justify-content: flex-start; text-align: center; cursor: pointer; transition: 0.15s;
            position: relative; padding: 8px 4px; box-sizing: border-box;
        }
        .spell-card:hover { transform: translateY(-4px); background: var(--bg-hover); border-color: #777;}
        .spell-card.used { opacity: 0.2; pointer-events: none; filter: grayscale(100%); }
        
        .spell-icon { font-size: 1.8rem; margin-bottom: 8px; margin-top: 5px; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .spell-name { font-size: 0.75rem; font-weight: bold; line-height: 1.1; color: #fff; }
        
        .spell-card.Legendary { border-bottom: 4px solid var(--gold); }
        .spell-card.Rare { border-bottom: 4px solid var(--purple); }
        .spell-card.Common { border-bottom: 4px solid var(--silver); }

        /* Right Sidebar (Moves & Chat) */
        .sidebar {
            width: 350px;
            background: var(--bg-sidebar);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            height: 620px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        }

        .sidebar-tabs {
            display: flex; background: var(--bg-panel); border-bottom: 1px solid var(--border-color);
        }
        .sidebar-tab {
            flex: 1; text-align: center; padding: 12px; font-weight: bold; color: var(--text-main);
            border-bottom: 2px solid var(--accent-green);
        }

        .sidebar-content {
            flex: 1; overflow-y: auto; display: flex; flex-direction: column;
        }

        /* Move List Table */
        .move-history {
            display: grid; grid-template-columns: 40px 1fr 1fr; font-size: 0.95rem; font-family: monospace;
        }
        .move-row { display: contents; }
        .move-row > div { padding: 8px 10px; border-bottom: 1px solid var(--border-color); }
        .move-num { background: var(--bg-panel); color: var(--text-muted); text-align: right;}
        .move-ply { color: #fff; font-weight: bold; }
        .move-ply.spell-move { color: var(--purple); }

        /* Lobby / Share Link Box */
        .lobby-box {
            padding: 20px; text-align: center; background: var(--bg-panel); border-top: 1px solid var(--border-color);
        }
        .lobby-box h3 { margin: 0 0 10px 0; font-size: 1rem; color: #fff;}
        .lobby-box input {
            width: 90%; padding: 8px; background: #111; color: #fff; border: 1px solid #444; border-radius: 4px; margin-bottom: 10px; font-family: monospace;
        }
        .btn-green {
            background-color: var(--accent-green); color: white; border: none; width: 95%;
            padding: 12px; font-weight: bold; border-radius: 4px; cursor: pointer;
            text-transform: uppercase; font-size: 0.95rem; transition: 0.2s;
        }
        .btn-green:hover { background-color: var(--accent-green-hover); }

        /* Modals & Overlays */
        .modal-overlay {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.85); z-index: 2000; justify-content: center; align-items: center;
        }
        .modal-content {
            background: var(--bg-panel); padding: 30px; border-radius: 8px; width: 90%; max-width: 650px;
            max-height: 85vh; overflow-y: auto; border: 1px solid var(--border-color); color: var(--text-main);
        }
        .modal-content h2 { color: #fff; margin-top: 0; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;}
        
        .grimoire-list { display: flex; flex-direction: column; gap: 10px; margin-top: 15px; }
        .grimoire-item { display: flex; align-items: center; gap: 15px; background: var(--bg-main); padding: 10px; border-radius: 4px; }
        .grimoire-icon { font-size: 1.5rem; width: 40px; text-align: center;}
        .grimoire-text h4 { margin: 0 0 4px 0; color: #fff;}
        .grimoire-text p { margin: 0; font-size: 0.85rem; color: #ccc;}

        #notification {
            position: fixed; top: 40%; left: 50%; transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.9); color: #fff; padding: 15px 30px;
            border-radius: 8px; border: 2px solid var(--purple); font-size: 1.2rem;
            font-weight: bold; display: none; z-index: 1000; text-align: center;
            box-shadow: 0 0 20px var(--magic-glow);
        }
    </style>
</head>
<body>

    <div id="header-bar">
        <div class="header-logo">♞ Wizard's Chess</div>
        <button class="info-btn" onclick="$('#rules-modal').css('display', 'flex')">i</button>
    </div>

    <div id="notification"></div>

    <div class="main-container">
        <!-- Center Board Column -->
        <div class="board-wrapper">
            
            <!-- Opponent Tag -->
            <div class="player-tag">
                <div class="player-info">
                    <div class="user-block">
                        <div class="avatar">P2</div>
                        <span id="opp-name">Opponent (Connecting...)</span>
                    </div>
                    <div class="clock" id="clock-opp">10:00</div>
                </div>
                <div class="captured-area" id="opp-captured"></div>
            </div>

            <!-- Board -->
            <div class="board-core" id="board-wrap">
                <div id="board"></div>
            </div>
            
            <div id="spell-instruction"></div>

            <!-- My Tag -->
            <div class="player-tag">
                <div class="captured-area" id="my-captured" style="margin-top: 0; margin-bottom: 4px;"></div>
                <div class="player-info">
                    <div class="user-block">
                        <div class="avatar" style="background: var(--accent-green); color: #000;">P1</div>
                        <span id="my-name">You</span>
                    </div>
                    <div class="clock active" id="clock-my">10:00</div>
                </div>
            </div>

            <!-- My Spell Deck -->
            <div class="deck-container">
                <div class="deck-title">Your Hand</div>
                <div class="spells-row" id="spells-view"></div>
            </div>
        </div>

        <!-- Right Sidebar -->
        <div class="sidebar">
            <div class="sidebar-tabs">
                <div class="sidebar-tab">Match Telemetry</div>
            </div>
            
            <div class="sidebar-content">
                <div class="move-history" id="move-history">
                    <!-- Moves will be appended here -->
                </div>
            </div>
            
            <div class="lobby-box" id="lobby-box">
                <h3>Play a Friend</h3>
                <input type="text" id="shareLink" readonly>
                <button class="btn-green" onclick="copyLink()">Copy Link</button>
            </div>
        </div>
    </div>

    <!-- INSTRUCTION MANUAL MODAL -->
    <div class="modal-overlay" id="rules-modal">
        <div class="modal-content">
            <h2>How to Play Wizard's Chess</h2>
            <p><strong>The Deck:</strong> Out of 10 total spells, you are randomly dealt exactly 6 (1 Legendary, 2 Rares, 3 Commons).</p>
            <p><strong>Fully Automated Magic:</strong> Unlike tabletop simulators, this engine enforces magic automatically. Click a spell in your hand to activate it. The board will glow, and an instruction bar will tell you what to click or drag. Once resolved, your turn automatically ends.</p>
            <p style="color: var(--accent-green);"><strong>Note:</strong> Spells cannot be used to directly capture or target a King.</p>
            
            <h3 style="margin-top: 25px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">The Grimoire (All 10 Automated Spells)</h3>
            <div class="grimoire-list">
                <!-- Legendary -->
                <div class="grimoire-item"><div class="grimoire-icon">⚡</div><div class="grimoire-text"><h4 style="color:var(--gold);">Avada Kedavra (Legendary)</h4><p>Click an enemy piece to instantly destroy it.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">⏳</div><div class="grimoire-text"><h4 style="color:var(--gold);">Time-Turner (Legendary)</h4><p>Instantly rewinds the board to the previous round.</p></div></div>
                <!-- Rare -->
                <div class="grimoire-item"><div class="grimoire-icon">👁️</div><div class="grimoire-text"><h4 style="color:var(--purple);">Imperio (Rare)</h4><p>Drag and drop an enemy piece to make a legal move for them.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🩸</div><div class="grimoire-text"><h4 style="color:var(--purple);">Sectumsempra (Rare)</h4><p>Click an enemy piece. It is instantly demoted into a Pawn.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🔥</div><div class="grimoire-text"><h4 style="color:var(--purple);">Fiendfyre (Rare)</h4><p>Click any square. Destroys the piece on it and all 8 surrounding pieces.</p></div></div>
                <!-- Common -->
                <div class="grimoire-item"><div class="grimoire-icon">🧲</div><div class="grimoire-text"><h4 style="color:var(--silver);">Accio (Common)</h4><p>Drag one of your pieces up to 2 squares in any direction (ignores blockers).</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🪶</div><div class="grimoire-text"><h4 style="color:var(--silver);">Wingardium Leviosa (Common)</h4><p>Drag one of your pieces to any adjacent empty square.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🗝️</div><div class="grimoire-text"><h4 style="color:var(--silver);">Alohomora (Common)</h4><p>Drag one of your pieces to any empty square on your half of the board.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🪄</div><div class="grimoire-text"><h4 style="color:var(--silver);">Expelliarmus (Common)</h4><p>Instantly forces the opponent to skip their next turn. You move twice.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🛡️</div><div class="grimoire-text"><h4 style="color:var(--silver);">Protego (Common)</h4><p>Click one of your Pawns to instantly promote it to a Knight.</p></div></div>
            </div>

            <button class="btn-green" style="margin-top: 20px; width: 100%;" onclick="$('#rules-modal').hide()">Close Manual</button>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>

    <script>
        const sfxMove = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3');
        const sfxCapture = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3');
        const sfxStart = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/game-start.mp3');
        const sfxSpell = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3');

        const socket = io();
        const urlParams = new URLSearchParams(window.location.search);
        let room = urlParams.get('room');
        if (!room) {
            room = Math.random().toString(36).substring(2, 9);
            window.history.pushState({}, '', `?room=${room}`);
        }
        document.getElementById('shareLink').value = window.location.href;
        socket.emit('join_room', room);

        function copyLink() {
            const copyText = document.getElementById("shareLink");
            copyText.select();
            document.execCommand("copy");
            $('.lobby-box .btn-green').text("Copied!");
            setTimeout(() => $('.lobby-box .btn-green').text("Copy Link"), 2000);
        }

        function showPopup(msg) {
            $('#notification').html(msg).fadeIn(200);
            setTimeout(() => $('#notification').fadeOut(500), 2500);
        }

        // FULL 10 SPELL DICTIONARY (STATELESS AUTOMATION)
        const ALL_SPELLS = [
            { id: 'avada', name: 'Avada Kedavra', rarity: 'Legendary', icon: '⚡', action: 'click', desc: 'Click an enemy piece to destroy it.' },
            { id: 'time', name: 'Time-Turner', rarity: 'Legendary', icon: '⏳', action: 'instant', desc: 'Instantly rewinds the board 1 round.' },
            { id: 'imperio', name: 'Imperio', rarity: 'Rare', icon: '👁️', action: 'drag', desc: 'Drag an enemy piece to move it for them.' },
            { id: 'sectum', name: 'Sectumsempra', rarity: 'Rare', icon: '🩸', action: 'click', desc: 'Click an enemy piece to demote it to a Pawn.' },
            { id: 'fiendfyre', name: 'Fiendfyre', rarity: 'Rare', icon: '🔥', action: 'click', desc: 'Click a square. Destroys it and adjacent squares.' },
            { id: 'accio', name: 'Accio', rarity: 'Common', icon: '🧲', action: 'drag', desc: 'Drag your piece up to 2 squares (ignores rules).' },
            { id: 'leviosa', name: 'Leviosa', rarity: 'Common', icon: '🪶', action: 'drag', desc: 'Drag your piece to any adjacent empty square.' },
            { id: 'alohomora', name: 'Alohomora', rarity: 'Common', icon: '🗝️', action: 'drag', desc: 'Drag your piece to any empty square in your half.' },
            { id: 'expelliarmus', name: 'Expelliarmus', rarity: 'Common', icon: '🪄', action: 'instant', desc: 'Opponent skips next turn. You move again.' },
            { id: 'protego', name: 'Protego', rarity: 'Common', icon: '🛡️', action: 'click', desc: 'Click your Pawn to instantly promote it to a Knight.' }
        ];

        function shuffle(arr) { return arr.sort(() => 0.5 - Math.random()); }
        
        // Exact Deck Generation: 1 Leg, 2 Rare, 3 Common
        let myHand = [
            ...shuffle(ALL_SPELLS.filter(s => s.rarity === 'Legendary')).slice(0, 1),
            ...shuffle(ALL_SPELLS.filter(s => s.rarity === 'Rare')).slice(0, 2),
            ...shuffle(ALL_SPELLS.filter(s => s.rarity === 'Common')).slice(0, 3)
        ];

        let board = null;
        let game = new Chess();
        let myColor = null;
        let activeSpell = null;
        let fenHistory = [game.fen()];
        let currentMoveNum = 1;

        // Visual Clocks
        let timeW = 600, timeB = 600;
        function formatTime(s) { let m=Math.floor(s/60), sec=s%60; return m+":"+(sec<10?"0":"")+sec; }
        setInterval(() => {
            if(game.game_over() || !myColor) return;
            if(game.turn() === 'w') timeW--; else timeB--;
            $('#clock-my').text(formatTime(myColor==='w'?timeW:timeB));
            $('#clock-opp').text(formatTime(myColor==='w'?timeB:timeW));
        }, 1000);

        // Captured Pieces Logic
        const pieceValues = { 'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9 };
        const baseCounts = { 'p': 8, 'n': 2, 'b': 2, 'r': 2, 'q': 1 };
        
        function updateCapturedPieces() {
            let currentFEN = game.fen().split(' ')[0];
            let counts = { w: {p:0, n:0, b:0, r:0, q:0}, b: {p:0, n:0, b:0, r:0, q:0} };
            
            for (let char of currentFEN) {
                if (char >= 'a' && char <= 'z' && counts.b[char] !== undefined) counts.b[char]++;
                if (char >= 'A' && char <= 'Z' && counts.w[char.toLowerCase()] !== undefined) counts.w[char.toLowerCase()]++;
            }

            let capByWhite = '', capByBlack = '';
            let whiteScore = 0, blackScore = 0;

            ['q', 'r', 'b', 'n', 'p'].forEach(p => {
                let wMissing = baseCounts[p] - counts.w[p];
                let bMissing = baseCounts[p] - counts.b[p];
                
                for(let i=0; i<bMissing; i++) {
                    capByWhite += `<div class="captured-piece" style="background-image:url('https://chessboardjs.com/img/chesspieces/wikipedia/b${p.toUpperCase()}.png')"></div>`;
                    whiteScore += pieceValues[p];
                }
                for(let i=0; i<wMissing; i++) {
                    capByBlack += `<div class="captured-piece" style="background-image:url('https://chessboardjs.com/img/chesspieces/wikipedia/w${p.toUpperCase()}.png')"></div>`;
                    blackScore += pieceValues[p];
                }
            });

            let wAdv = whiteScore - blackScore;
            let bAdv = blackScore - whiteScore;

            if (wAdv > 0) capByWhite += `<span class="material-adv">+${wAdv}</span>`;
            if (bAdv > 0) capByBlack += `<span class="material-adv">+${bAdv}</span>`;

            if (myColor === 'w') {
                $('#my-captured').html(capByWhite);
                $('#opp-captured').html(capByBlack);
            } else {
                $('#my-captured').html(capByBlack);
                $('#opp-captured').html(capByWhite);
            }
        }

        function appendMove(text, isSpell=false) {
            if (isSpell) {
                $('#move-history').append(`<div class="move-row"><div></div><div class="move-ply spell-move" style="grid-column: span 2;">✨ ${text}</div></div>`);
            } else {
                if (game.turn() === 'b') {
                    $('#move-history').append(`<div class="move-row"><div class="move-num">${currentMoveNum}.</div><div class="move-ply">${text}</div></div>`);
                } else {
                    $('#move-history .move-row:last-child').append(`<div class="move-ply">${text}</div>`);
                    currentMoveNum++;
                }
            }
            $('.sidebar-content').scrollTop($('.sidebar-content')[0].scrollHeight);
        }

        socket.on('role_assigned', (color) => {
            myColor = color;
            
            // Render Hand
            myHand.forEach(s => {
                const card = $(`
                    <div class="spell-card ${s.rarity}" id="${s.id}" title="${s.desc}">
                        <div class="spell-icon">${s.icon}</div>
                        <div class="spell-name">${s.name}</div>
                    </div>
                `);
                
                // CRITICAL TURN-LOCK LOGIC
                card.on('click', function() {
                    if (game.turn() !== myColor) {
                        showPopup(`⚠️ You can only cast spells on your turn!`);
                        return;
                    }
                    if(!$(this).hasClass('used')) {
                        $(this).addClass('used');
                        sfxSpell.play();
                        socket.emit('spell_cast', { name: s.name });
                        
                        // INSTANT SPELL RESOLUTION
                        if (s.action === 'instant') {
                            if (s.id === 'time') {
                                if (fenHistory.length >= 3) {
                                    game.load(fenHistory[fenHistory.length - 3]);
                                    endMagicTurn(s.name);
                                } else { showPopup("Not enough history to rewind!"); }
                            }
                            else if (s.id === 'expelliarmus') {
                                // Sync board without changing turn. Opponent is skipped!
                                socket.emit('magic_sync', game.fen());
                                appendMove(`EXPELLIARMUS`, true);
                                showPopup("Opponent Turn Skipped!");
                            }
                            return;
                        }

                        // CLICK / DRAG ACTIVATION
                        activeSpell = s;
                        $('#board-wrap').addClass('magic-active');
                        $('#spell-instruction').html(`🪄 <b>${s.name.toUpperCase()}</b>: ${s.desc}`).fadeIn(200);
                    }
                });
                $('#spells-view').append(card);
            });

            if (myColor === 'b') {
                board.orientation('black');
                $('#my-name').text('You (Black)');
                $('#opp-name').text('Opponent (White)');
            } else {
                $('#my-name').text('You (White)');
                $('#opp-name').text('Opponent (Black)');
            }
            updateStatusUI();
        });

        socket.on('user_joined', () => {
            $('#lobby-box').slideUp(300);
            sfxStart.play();
            updateStatusUI();
        });

        socket.on('standard_move', (move) => {
            let res = game.move(move);
            board.position(game.fen());
            fenHistory.push(game.fen());
            
            if (res && res.captured) sfxCapture.play();
            else sfxMove.play();
            
            appendMove(`${move.from}-${move.to}`);
            updateCapturedPieces();
            updateStatusUI();
        });

        socket.on('magic_sync', (fenState) => {
            game.load(fenState);
            board.position(fenState);
            fenHistory.push(fenState);
            sfxSpell.play();
            updateCapturedPieces();
            updateStatusUI();
        });

        socket.on('spell_cast', (spellData) => {
            sfxSpell.play();
            appendMove(`${spellData.name.toUpperCase()}`, true);
        });

        function updateStatusUI() {
            if(!myColor) return;
            if (game.turn() === myColor) {
                $('#clock-my').addClass('active');
                $('#clock-opp').removeClass('active');
            } else {
                $('#clock-opp').addClass('active');
                $('#clock-my').removeClass('active');
            }
        }

        function endMagicTurn(spellName) {
            activeSpell = null;
            $('#board-wrap').removeClass('magic-active');
            $('#spell-instruction').hide();

            // Force turn switch
            let tokens = game.fen().split(' ');
            tokens[1] = (myColor === 'w') ? 'b' : 'w';
            tokens[3] = '-'; // clear en passant
            let nextFen = tokens.join(' ');
            
            game.load(nextFen);
            fenHistory.push(nextFen);
            board.position(nextFen);
            
            appendMove(`${spellName.toUpperCase()}`, true);
            updateCapturedPieces();
            updateStatusUI();
            socket.emit('magic_sync', nextFen);
        }

        // CLICK RESOLUTION ENGINE
        $('#board').on('click', '.square-55d63', function() {
            if (!activeSpell || activeSpell.action !== 'click') return;
            let sq = $(this).attr('data-square');
            let p = game.get(sq);

            if (activeSpell.id === 'avada') {
                if (p && p.color !== myColor && p.type !== 'k') {
                    game.remove(sq); endMagicTurn(activeSpell.name);
                } else showPopup("Must click a non-King enemy piece.");
            }
            else if (activeSpell.id === 'sectum') {
                if (p && p.color !== myColor && p.type !== 'k') {
                    game.remove(sq); game.put({type:'p', color:p.color}, sq); endMagicTurn(activeSpell.name);
                } else showPopup("Must click an enemy piece.");
            }
            else if (activeSpell.id === 'fiendfyre') {
                let file = sq.charCodeAt(0), rank = parseInt(sq[1]);
                for(let f = file-1; f <= file+1; f++) {
                    for(let r = rank-1; r <= rank+1; r++) {
                        let targetSq = String.fromCharCode(f) + r;
                        let tP = game.get(targetSq);
                        if (tP && tP.type !== 'k') game.remove(targetSq);
                    }
                }
                endMagicTurn(activeSpell.name);
            }
            else if (activeSpell.id === 'protego') {
                if (p && p.color === myColor && p.type === 'p') {
                    game.remove(sq); game.put({type:'n', color:myColor}, sq); endMagicTurn(activeSpell.name);
                } else showPopup("Must click one of your Pawns.");
            }
        });

        // DRAG RESOLUTION ENGINE
        function onDragStart(source, piece) {
            if (game.game_over()) return false;
            
            // Spell Constraints
            if (activeSpell) {
                if (activeSpell.action !== 'drag') return false;
                if (activeSpell.id === 'imperio') return piece.charAt(0) !== myColor; // Must drag enemy
                return piece.charAt(0) === myColor; // Others must drag own
            }
            
            // Standard Constraints
            if (game.turn() !== myColor) return false;
            if ((myColor === 'w' && piece.search(/^b/) !== -1) || (myColor === 'b' && piece.search(/^w/) !== -1)) return false;
        }

        function onDrop(source, target) {
            if (activeSpell && activeSpell.action === 'drag') {
                let p = game.get(source);
                let tP = game.get(target);
                if (tP && tP.type === 'k') return 'snapback'; // Never destroy Kings magically

                let fDist = Math.abs(source.charCodeAt(0) - target.charCodeAt(0));
                let rDist = Math.abs(source[1] - target[1]);

                if (activeSpell.id === 'imperio') {
                    // Temporarily flip engine turn to validate enemy move
                    let tempFen = game.fen();
                    let tokens = tempFen.split(' ');
                    tokens[1] = (myColor === 'w') ? 'b' : 'w';
                    game.load(tokens.join(' '));
                    
                    let move = game.move({from: source, to: target, promotion: 'q'});
                    if (!move) { game.load(tempFen); return 'snapback'; }
                    
                    endMagicTurn(activeSpell.name);
                    return;
                }
                else if (activeSpell.id === 'accio') {
                    if (fDist <= 2 && rDist <= 2) {
                        game.remove(source); game.put(p, target); endMagicTurn(activeSpell.name); return;
                    } else return 'snapback';
                }
                else if (activeSpell.id === 'leviosa') {
                    if (fDist <= 1 && rDist <= 1 && !tP) {
                        game.remove(source); game.put(p, target); endMagicTurn(activeSpell.name); return;
                    } else return 'snapback';
                }
                else if (activeSpell.id === 'alohomora') {
                    let validRank = (myColor === 'w') ? target[1] <= 4 : target[1] >= 5; // Half of board
                    if (!tP && validRank) {
                        game.remove(source); game.put(p, target); endMagicTurn(activeSpell.name); return;
                    } else return 'snapback';
                }
                return 'snapback';
            }

            // STANDARD MOVE
            let move = game.move({ from: source, to: target, promotion: 'q' });
            if (move === null) return 'snapback';
            
            fenHistory.push(game.fen());
            appendMove(`${source}-${target}`);

            if (move.captured) sfxCapture.play();
            else sfxMove.play();

            socket.emit('standard_move', { from: source, to: target, promotion: 'q' });
            updateCapturedPieces();
            updateStatusUI();
        }

        function onSnapEnd() {
            if(!activeSpell) board.position(game.fen());
        }

        board = Chessboard('board', {
            draggable: true, position: 'start',
            onDragStart: onDragStart, onDrop: onDrop, onSnapEnd: onSnapEnd,
            pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png'
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"> SERVER ONLINE. PORT: {port}")
    socketio.run(app, host='0.0.0.0', port=port)
