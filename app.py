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
            --bg-main: #302e2b;
            --bg-panel: #262421;
            --text-main: #fff;
            --text-muted: #989795;
            --accent-green: #81b64c;
            --gold: #f5b041;
            --purple: #a855f7;
            --silver: #9ca3af;
            --magic-glow: rgba(168, 85, 247, 0.6);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100vh;
            overflow: hidden;
        }

        /* Top Header & Invite Banner */
        #header-bar {
            width: 100%;
            background: #21201d;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-sizing: border-box;
            border-bottom: 2px solid #1a1917;
        }
        .invite-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .invite-group input {
            padding: 8px; width: 300px; background: #111; color: #fff;
            border: 1px solid #444; border-radius: 4px; font-family: monospace;
        }
        .btn {
            background-color: var(--accent-green); color: white; border: none;
            padding: 8px 16px; font-weight: bold; border-radius: 4px; cursor: pointer;
        }
        .btn:hover { background-color: #a3d160; }
        .info-btn {
            background: #444; color: #fff; border-radius: 50%; width: 30px; height: 30px;
            display: flex; align-items: center; justify-content: center; font-weight: bold;
            cursor: pointer; border: none;
        }

        /* Modals */
        .modal-overlay {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); z-index: 2000; justify-content: center; align-items: center;
        }
        .modal-content {
            background: var(--bg-panel); padding: 30px; border-radius: 8px; max-width: 600px;
            border: 1px solid #444; color: var(--text-main); line-height: 1.5;
        }
        .modal-content h2 { color: var(--gold); margin-top: 0; }

        /* Main Game Layout (2 Columns) */
        .game-layout {
            display: grid;
            grid-template-columns: 320px 550px;
            gap: 40px;
            margin-top: 30px;
            justify-content: center;
        }

        /* Spells Column */
        .spell-column {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .hand-title {
            font-size: 1.1rem; font-weight: bold; padding-bottom: 10px;
            border-bottom: 1px solid #444; margin-bottom: 5px;
        }
        .card {
            background-color: var(--bg-panel); border: 1px solid #444; padding: 12px;
            border-radius: 6px; cursor: pointer; position: relative; transition: 0.2s;
            border-left-width: 4px;
        }
        .card:hover { transform: translateX(5px); }
        .card.used { opacity: 0.3; pointer-events: none; filter: grayscale(100%); }
        .card-title { font-weight: bold; margin-bottom: 4px; font-size: 1rem; }
        .card-effect { font-size: 0.85rem; color: #ccc; }
        
        /* Rarity Colors */
        .card.Legendary { border-left-color: var(--gold); }
        .card.Legendary .card-title { color: var(--gold); }
        .card.Rare { border-left-color: var(--purple); }
        .card.Rare .card-title { color: var(--purple); }
        .card.Common { border-left-color: var(--silver); }
        .card.Common .card-title { color: var(--silver); }

        /* Board Column & Player Tags */
        .board-col { display: flex; flex-direction: column; width: 550px; }
        
        .player-tag {
            display: flex; flex-direction: column; justify-content: center;
            padding: 8px 0; min-height: 50px;
        }
        .player-info {
            display: flex; align-items: center; justify-content: space-between; font-weight: bold; font-size: 1.1rem;
        }
        .status-badge {
            font-size: 0.8rem; padding: 3px 8px; border-radius: 12px; background: #444; color: #fff;
        }
        .status-badge.active { background: var(--accent-green); }

        /* Captured Pieces UI */
        .captured-area {
            display: flex; align-items: center; height: 25px; margin-top: 2px;
        }
        .captured-piece {
            width: 22px; height: 22px; background-size: cover; margin-right: -8px;
        }
        .material-adv {
            margin-left: 15px; font-size: 0.9rem; font-weight: bold; color: var(--text-muted);
        }

        /* The Board */
        .board-container {
            border-radius: 4px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); transition: 0.3s;
        }
        .board-container.magic-active {
            box-shadow: 0 0 40px var(--magic-glow); border: 2px solid var(--purple);
        }
        #board { width: 100%; }

        /* Overlays */
        #notification {
            position: fixed; top: 40%; left: 50%; transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.9); color: var(--gold); padding: 15px 30px;
            border-radius: 8px; border: 2px solid var(--gold); font-size: 1.2rem;
            font-weight: bold; display: none; z-index: 1000; text-align: center;
        }
        .legal-dot::after {
            content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: 25%; height: 25%; background-color: rgba(0,0,0,0.2); border-radius: 50%;
        }
    </style>
</head>
<body>

    <!-- Header & Invite -->
    <div id="header-bar">
        <div style="font-weight: bold; font-size: 1.2rem; color: var(--gold);">Wizard's Chess</div>
        <div class="invite-group" id="invite-group">
            <span>Waiting for Opponent...</span>
            <input type="text" id="shareLink" readonly>
            <button class="btn" onclick="copyLink()">Copy Link</button>
        </div>
        <button class="info-btn" onclick="$('#rules-modal').css('display', 'flex')">i</button>
    </div>

    <div id="notification"></div>

    <div class="game-layout">
        
        <!-- Left: Spells -->
        <div class="spell-column">
            <div class="hand-title">Your Spell Hand</div>
            <div id="spells-view" style="display: flex; flex-direction: column; gap: 10px;"></div>
        </div>

        <!-- Right: Board Area -->
        <div class="board-col">
            <!-- Opponent Tag -->
            <div class="player-tag">
                <div class="player-info">
                    <span id="opp-name">Opponent (Connecting...)</span>
                    <span id="opp-status" class="status-badge">Waiting</span>
                </div>
                <div class="captured-area" id="opp-captured"></div>
            </div>

            <!-- Board -->
            <div class="board-container" id="board-wrap">
                <div id="board"></div>
            </div>

            <!-- My Tag -->
            <div class="player-tag">
                <div class="player-info">
                    <span id="my-name">You</span>
                    <span id="my-status" class="status-badge active">Your Turn</span>
                </div>
                <div class="captured-area" id="my-captured"></div>
            </div>
        </div>
    </div>

    <!-- Instructions Modal -->
    <div class="modal-overlay" id="rules-modal">
        <div class="modal-content">
            <h2>How to Play Wizard's Chess</h2>
            <p><strong>The Deck:</strong> Out of 10 total spells, you are randomly dealt exactly 6 (1 Legendary, 2 Rares, 3 Commons).</p>
            <p><strong>Casting Magic:</strong> Click a spell in your hand to activate it. The board will glow purple. You are now in <b>Magic Mode</b>.</p>
            <p><strong>Resolving Effects:</strong> While the board is glowing, you can drag, drop, or throw pieces off the board to match your spell's description. Once you drop the piece, your turn ends and standard chess rules automatically lock back in.</p>
            <p><strong>Note:</strong> Spells cannot be used to directly capture a King.</p>
            <button class="btn" style="margin-top: 15px;" onclick="$('#rules-modal').hide()">Understood</button>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>

    <script>
        // Official Audio
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
            $('.invite-group .btn').text("Copied!");
            setTimeout(() => $('.invite-group .btn').text("Copy Link"), 2000);
        }

        function showPopup(msg) {
            $('#notification').html(msg).fadeIn(200);
            setTimeout(() => $('#notification').fadeOut(500), 2500);
        }

        // --- 10 SPELL POOL & RANDOMIZER ---
        const poolLegendary = [
            { name: "Avada Kedavra", rarity: "Legendary", effect: "Drag an enemy piece off the board to instantly destroy it." },
            { name: "Time-Turner", rarity: "Legendary", effect: "Rewind or alter a previous board state." }
        ];
        const poolRare = [
            { name: "Imperio", rarity: "Rare", effect: "Commandeer an opponent's piece and move it yourself." },
            { name: "Sectumsempra", rarity: "Rare", effect: "Target enemy piece cannot move for two turns." },
            { name: "Expecto Patronum", rarity: "Rare", effect: "Shields an area of the board." },
            { name: "Fiendfyre", rarity: "Rare", effect: "Destroys multiple clustered pieces." }
        ];
        const poolCommon = [
            { name: "Accio", rarity: "Common", effect: "Pull one of your pieces up to 2 squares in any direction." },
            { name: "Wingardium Leviosa", rarity: "Common", effect: "Float one of your pieces to any adjacent empty square." },
            { name: "Alohomora", rarity: "Common", effect: "Move one piece through occupied friendly pieces." },
            { name: "Protego", rarity: "Common", effect: "One of your pieces is shielded from capture next turn." }
        ];

        function shuffle(arr) { return arr.sort(() => 0.5 - Math.random()); }
        
        // Draw 6 cards exactly
        let myHand = [
            ...shuffle(poolLegendary).slice(0, 1),
            ...shuffle(poolRare).slice(0, 2),
            ...shuffle(poolCommon).slice(0, 3)
        ];

        // --- GAME STATE ---
        let board = null;
        let game = new Chess();
        let myColor = null;
        let isMagicModeActive = false; // The invisible engine toggle

        // --- RENDER CAPTURED PIECES (CHESS.COM STYLE) ---
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

        // --- NETWORK EVENTS ---
        socket.on('role_assigned', (color) => {
            myColor = color;
            
            // Render Hand
            myHand.forEach((s, idx) => {
                const card = $(`
                    <div class="card ${s.rarity}" id="card-${idx}">
                        <div class="card-title">${s.name}</div>
                        <div class="card-effect">${s.effect}</div>
                    </div>
                `);
                
                // SPELL EXECUTION
                card.on('click', function() {
                    if(!$(this).hasClass('used')) {
                        $(this).addClass('used');
                        sfxSpell.play();
                        
                        socket.emit('spell_cast', { name: s.name });
                        
                        // Activate invisible magic engine
                        isMagicModeActive = true;
                        $('#board-wrap').addClass('magic-active');
                        showPopup(`✨ <b>${s.name.toUpperCase()}</b><br><span style="font-size:1rem;">Board Unlocked. Execute your magic.</span>`);
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
            showPopup('Game Started!');
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
            game.load(fenState + " w - - 0 1");
            board.position(fenState);
            sfxSpell.play();
            updateCapturedPieces();
            updateStatusUI();
        });

        socket.on('spell_cast', (spellData) => {
            sfxSpell.play();
            showPopup(`Opponent used<br><b>${spellData.name.toUpperCase()}</b>`);
        });


        // --- UI STATUS UPDATER ---
        function updateStatusUI() {
            if(!myColor) return;
            if (game.turn() === myColor) {
                $('#my-status').addClass('active').text('Your Turn');
                $('#opp-status').removeClass('active').text('Waiting');
            } else {
                $('#opp-status').addClass('active').text('Thinking');
                $('#my-status').removeClass('active').text('Waiting');
            }
        }

        // --- BOARD INTERACTION ---
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
            
            // --- RESOLVE MAGIC SPELL ---
            if (isMagicModeActive) {
                if (source === target) return 'snapback';
                
                sfxSpell.play();
                
                // Turn off magic mode immediately after drop
                isMagicModeActive = false;
                $('#board-wrap').removeClass('magic-active');

                // Force standard engine to accept chaos
                setTimeout(() => {
                    const nextFen = board.fen();
                    game.load(nextFen + " w - - 0 1"); 
                    socket.emit('magic_sync', nextFen);
                    updateCapturedPieces();
                }, 100);
                return;
            }

            // --- STANDARD MOVE ---
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
            draggable: true,
            dropOffBoard: 'trash', // Throw pieces off board for Avada Kedavra
            position: 'start',
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
