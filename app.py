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
            --bg-panel: #262421;
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

        .invite-group {
            display: flex;
            align-items: center;
            gap: 10px;
            background: var(--bg-panel);
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }

        .invite-group input {
            padding: 6px; width: 280px; background: #111; color: #fff;
            border: 1px solid #444; border-radius: 4px; font-family: monospace; font-size: 0.85rem;
        }

        .btn-green {
            background-color: var(--accent-green); color: white; border: none;
            padding: 8px 16px; font-weight: bold; border-radius: 4px; cursor: pointer;
            text-transform: uppercase; font-size: 0.85rem; transition: 0.2s;
        }
        .btn-green:hover { background-color: var(--accent-green-hover); }

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
            max-width: 1200px;
            flex-wrap: wrap;
        }

        .board-wrapper {
            display: flex;
            flex-direction: column;
            width: 550px;
        }

        /* Player Tags & Captured Pieces */
        .player-tag {
            display: flex; flex-direction: column; justify-content: center;
            padding: 10px 0; min-height: 50px;
        }
        .player-info {
            display: flex; align-items: center; justify-content: space-between; font-weight: bold; font-size: 1rem;
        }
        
        .user-block { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 32px; height: 32px; background: #555; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
        
        .status-badge { font-size: 0.75rem; padding: 3px 8px; border-radius: 12px; background: #444; color: #fff; text-transform: uppercase; font-weight: 800;}
        .status-badge.active { background: var(--accent-green); }

        .captured-area { display: flex; align-items: center; height: 25px; margin-top: 4px; padding-left: 42px; }
        .captured-piece { width: 22px; height: 22px; background-size: cover; margin-right: -8px; }
        .material-adv { margin-left: 15px; font-size: 0.85rem; font-weight: bold; color: var(--text-muted); }

        /* The Board */
        .board-core {
            border-radius: 4px; box-shadow: 0 4px 15px rgba(0,0,0,0.4); transition: 0.3s;
            border: 2px solid transparent;
        }
        .board-core.magic-active {
            box-shadow: 0 0 40px var(--magic-glow); border: 2px solid var(--purple);
        }
        #board { width: 100%; }

        .deck-container {
            margin-top: 15px;
            background: var(--bg-panel);
            padding: 15px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
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
            position: relative; padding: 8px 4px;
        }
        .spell-card:hover { transform: translateY(-4px); background: var(--bg-hover); }
        .spell-card.used { opacity: 0.2; pointer-events: none; filter: grayscale(100%); }
        
        .spell-icon { font-size: 1.8rem; margin-bottom: 8px; margin-top: 5px; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .spell-name { font-size: 0.75rem; font-weight: bold; line-height: 1.1; color: #fff; }
        
        .spell-card.Legendary { border-bottom: 4px solid var(--gold); }
        .spell-card.Rare { border-bottom: 4px solid var(--purple); }
        .spell-card.Common { border-bottom: 4px solid var(--silver); }

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
        .legal-dot::after {
            content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: 25%; height: 25%; background-color: rgba(0,0,0,0.3); border-radius: 50%;
        }
    </style>
</head>
<body>

    <div id="header-bar">
        <div class="header-logo">♞ Wizard's Chess</div>
        <div class="invite-group" id="invite-group">
            <span style="font-size: 0.85rem; font-weight: bold; color: var(--text-muted);">WAITING FOR OPPONENT:</span>
            <input type="text" id="shareLink" readonly>
            <button class="btn-green" onclick="copyLink()">Copy</button>
        </div>
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
                    <span id="opp-status" class="status-badge">Waiting</span>
                </div>
                <div class="captured-area" id="opp-captured"></div>
            </div>

            <!-- Board -->
            <div class="board-core" id="board-wrap">
                <div id="board"></div>
            </div>

            <!-- My Tag -->
            <div class="player-tag">
                <div class="captured-area" id="my-captured" style="margin-top: 0; margin-bottom: 4px;"></div>
                <div class="player-info">
                    <div class="user-block">
                        <div class="avatar" style="background: var(--accent-green); color: #000;">P1</div>
                        <span id="my-name">You</span>
                    </div>
                    <span id="my-status" class="status-badge active">Your Turn</span>
                </div>
            </div>

            <!-- My Spell Deck (Horizontal) -->
            <div class="deck-container">
                <div class="deck-title">Your Hand</div>
                <div class="spells-row" id="spells-view"></div>
            </div>

        </div>
    </div>

    <div class="modal-overlay" id="rules-modal">
        <div class="modal-content">
            <h2>How to Play Wizard's Chess</h2>
            <p><strong>The Deck:</strong> Out of 10 total spells, you are randomly dealt exactly 6 (1 Legendary, 2 Rares, 3 Commons).</p>
            <p><strong>Casting Magic:</strong> Click a spell in your hand to activate it. The board will glow purple. You are now in <b>Magic Mode</b>.</p>
            <p><strong>Resolving Effects:</strong> While the board is glowing, you can drag, drop, or throw pieces off the board to match your spell's description. Once you drop the piece, your turn ends and standard chess rules automatically lock back in.</p>
            <p style="color: var(--accent-green);"><strong>Note:</strong> Spells cannot be used to directly capture a King.</p>
            
            <h3 style="margin-top: 25px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">The Grimoire (All 10 Spells)</h3>
            <div class="grimoire-list">
                <!-- Legendary -->
                <div class="grimoire-item"><div class="grimoire-icon">⚡</div><div class="grimoire-text"><h4 style="color:var(--gold);">Avada Kedavra (Legendary)</h4><p>Drag an enemy piece off the board to instantly destroy it.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">⏳</div><div class="grimoire-text"><h4 style="color:var(--gold);">Time-Turner (Legendary)</h4><p>Rewind or alter a previous board state.</p></div></div>
                <!-- Rare -->
                <div class="grimoire-item"><div class="grimoire-icon">👁️</div><div class="grimoire-text"><h4 style="color:var(--purple);">Imperio (Rare)</h4><p>Commandeer an opponent's piece and move it yourself.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">⚔️</div><div class="grimoire-text"><h4 style="color:var(--purple);">Sectumsempra (Rare)</h4><p>Target enemy piece cannot move for two turns.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🛡️</div><div class="grimoire-text"><h4 style="color:var(--purple);">Expecto Patronum (Rare)</h4><p>Shields an area of the board.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🔥</div><div class="grimoire-text"><h4 style="color:var(--purple);">Fiendfyre (Rare)</h4><p>Destroys multiple clustered pieces.</p></div></div>
                <!-- Common -->
                <div class="grimoire-item"><div class="grimoire-icon">🧲</div><div class="grimoire-text"><h4 style="color:var(--silver);">Accio (Common)</h4><p>Pull one of your pieces up to 2 squares in any direction.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🪶</div><div class="grimoire-text"><h4 style="color:var(--silver);">Wingardium Leviosa (Common)</h4><p>Float one of your pieces to any adjacent empty square.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🗝️</div><div class="grimoire-text"><h4 style="color:var(--silver);">Alohomora (Common)</h4><p>Move one piece through occupied friendly pieces.</p></div></div>
                <div class="grimoire-item"><div class="grimoire-icon">🔰</div><div class="grimoire-text"><h4 style="color:var(--silver);">Protego (Common)</h4><p>One of your pieces is shielded from capture next turn.</p></div></div>
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
            $('.invite-group .btn-green').text("Copied!");
            setTimeout(() => $('.invite-group .btn-green').text("Copy"), 2000);
        }

        function showPopup(msg) {
            $('#notification').html(msg).fadeIn(200);
            setTimeout(() => $('#notification').fadeOut(500), 2500);
        }

        const poolLegendary = [
            { name: "Avada Kedavra", rarity: "Legendary", icon: "⚡", effect: "Drag an enemy piece off the board to destroy it." },
            { name: "Time-Turner", rarity: "Legendary", icon: "⏳", effect: "Rewind or alter a previous board state." }
        ];
        const poolRare = [
            { name: "Imperio", rarity: "Rare", icon: "👁️", effect: "Commandeer an opponent's piece." },
            { name: "Sectumsempra", rarity: "Rare", icon: "⚔️", effect: "Target cannot move for two turns." },
            { name: "Expecto Patronum", rarity: "Rare", icon: "🛡️", effect: "Shields an area of the board." },
            { name: "Fiendfyre", rarity: "Rare", icon: "🔥", effect: "Destroys multiple clustered pieces." }
        ];
        const poolCommon = [
            { name: "Accio", rarity: "Common", icon: "🧲", effect: "Pull a piece up to 2 squares." },
            { name: "Wingardium Leviosa", rarity: "Common", icon: "🪶", effect: "Float to an adjacent empty square." },
            { name: "Alohomora", rarity: "Common", icon: "🗝️", effect: "Move through occupied friendly pieces." },
            { name: "Protego", rarity: "Common", icon: "🔰", effect: "Shield from capture next turn." }
        ];

        function shuffle(arr) { return arr.sort(() => 0.5 - Math.random()); }
        
        // Exact Deck Generation: 1 Leg, 2 Rare, 3 Common
        let myHand = [
            ...shuffle(poolLegendary).slice(0, 1),
            ...shuffle(poolRare).slice(0, 2),
            ...shuffle(poolCommon).slice(0, 3)
        ];

        let board = null;
        let game = new Chess();
        let myColor = null;
        let isMagicModeActive = false;

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

        socket.on('role_assigned', (color) => {
            myColor = color;
            
            // Render Hand
            myHand.forEach((s, idx) => {
                const card = $(`
                    <div class="spell-card ${s.rarity}" id="card-${idx}" title="${s.effect}">
                        <div class="spell-icon">${s.icon}</div>
                        <div class="spell-name">${s.name}</div>
                    </div>
                `);
                
                card.on('click', function() {
                    if(!$(this).hasClass('used')) {
                        $(this).addClass('used');
                        sfxSpell.play();
                        socket.emit('spell_cast', { name: s.name });
                        
                        isMagicModeActive = true;
                        $('#board-wrap').addClass('magic-active');
                        showPopup(`✨ ${s.name.toUpperCase()}<br><span style="font-size:0.9rem; font-weight:normal;">Board Unlocked. Drag/drop to execute.</span>`);
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
            $('#invite-group').fadeOut(300);
            sfxStart.play();
            updateStatusUI();
            showPopup('Opponent Connected!<br>Game Started');
        });

        socket.on('standard_move', (move) => {
            let res = game.move(move);
            board.position(game.fen());
            
            if (res && res.captured) sfxCapture.play();
            else sfxMove.play();
            
            updateCapturedPieces();
            updateStatusUI();
        });

        socket.on('magic_sync', (fenState) => {
            game.load(fenState);
            board.position(fenState);
            sfxSpell.play();
            updateCapturedPieces();
            updateStatusUI();
        });

        socket.on('spell_cast', (spellData) => {
            sfxSpell.play();
            showPopup(`Opponent cast<br><span style="color:var(--purple);">${spellData.name.toUpperCase()}</span>`);
        });

        function updateStatusUI() {
            if(!myColor) return;
            if (game.turn() === myColor) {
                $('#my-status').addClass('active').text('Your Turn');
                $('#opp-status').removeClass('active').text('Waiting');
            } else {
                $('#opp-status').addClass('active').text('Thinking');
                $('#my-status').removeClass('active').text('Wait');
            }
        }

        function clearDots () { $('#board .square-55d63').removeClass('legal-dot'); }
        function drawDot (square) { $('#board .square-' + square).addClass('legal-dot'); }

        function onMouseoverSquare (square, piece) {
            if (isMagicModeActive || game.game_over() || game.turn() !== myColor) return;
            if (piece && piece.charAt(0) !== myColor) return;
            var moves = game.moves({ square: square, verbose: true });
            if (moves.length === 0) return;
            for (var i = 0; i < moves.length; i++) drawDot(moves[i].to);
        }

        function onMouseoutSquare () { clearDots(); }

        function onDragStart(source, piece) {
            if (isMagicModeActive) return true; // Magic Mode allows anything
            if (game.game_over() || game.turn() !== myColor) return false;
            if ((myColor === 'w' && piece.search(/^b/) !== -1) || (myColor === 'b' && piece.search(/^w/) !== -1)) return false;
        }

        function onDrop(source, target) {
            clearDots();
            
            // RESOLVE MAGIC SPELL
            if (isMagicModeActive) {
                if (source === target) return 'snapback';
                sfxSpell.play();
                isMagicModeActive = false;
                $('#board-wrap').removeClass('magic-active');

                // Force standard engine to accept chaos and switch turn
                setTimeout(() => {
                    let tokens = game.fen().split(' ');
                    tokens[0] = board.fen(); // apply new layout
                    tokens[1] = tokens[1] === 'w' ? 'b' : 'w'; // switch turn!
                    let nextFen = tokens.join(' ');
                    
                    let valid = game.load(nextFen);
                    if(!valid) { game.load(board.fen() + " " + tokens[1] + " - - 0 1"); } // fallback
                    
                    socket.emit('magic_sync', game.fen());
                    updateCapturedPieces();
                    updateStatusUI();
                }, 100);
                return;
            }

            // STANDARD MOVE
            let move = game.move({ from: source, to: target, promotion: 'q' });
            if (move === null) return 'snapback';
            
            if (move.captured) sfxCapture.play();
            else sfxMove.play();

            socket.emit('standard_move', { from: source, to: target, promotion: 'q' });
            updateCapturedPieces();
            updateStatusUI();
        }

        function onSnapEnd() {
            if(!isMagicModeActive) board.position(game.fen());
        }

        board = Chessboard('board', {
            draggable: true, dropOffBoard: 'trash', position: 'start',
            onDragStart: onDragStart, onDrop: onDrop, onSnapEnd: onSnapEnd,
            onMouseoutSquare: onMouseoutSquare, onMouseoverSquare: onMouseoverSquare,
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
