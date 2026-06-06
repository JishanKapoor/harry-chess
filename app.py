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
# NIBBLER-GUI INSPIRED MINIMALIST MULTIPLAYER INTERFACE
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
            --bg-main: #161512;
            --bg-panel: #262421;
            --bg-darker: #1e1c18;
            --border-ui: #363431;
            --text-main: #bababa;
            --text-light: #fff;
            --accent-green: #81b64c;
            --gold: #dfb15b;
            --magic-glow: rgba(138, 43, 226, 0.4);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100vh;
            overflow: hidden;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Invite Link Area */
        #invite-banner {
            background-color: var(--bg-panel);
            width: 100%;
            padding: 10px 0;
            text-align: center;
            border-bottom: 1px solid var(--border-ui);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            font-size: 0.95rem;
            z-index: 100;
            transition: opacity 0.3s ease;
        }
        #invite-banner input {
            padding: 6px 10px;
            width: 320px;
            background: var(--bg-main);
            color: var(--text-light);
            border: 1px solid var(--border-ui);
            border-radius: 3px;
            font-family: monospace;
            font-size: 0.85rem;
        }
        .btn-action {
            background-color: var(--accent-green);
            color: #fff;
            border: none;
            padding: 6px 14px;
            font-weight: 600;
            border-radius: 3px;
            cursor: pointer;
            transition: background 0.15s ease;
        }
        .btn-action:hover { background-color: #a3d160; }

        /* App Container Grid Layout */
        .app-container {
            display: grid;
            grid-template-columns: 260px 520px 320px;
            gap: 24px;
            margin-top: 25px;
            width: 100%;
            max-width: 1160px;
            height: calc(100vh - 100px);
        }

        /* Left Column: Hand Spells */
        .panel-left {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .panel-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-main);
            border-bottom: 1px solid var(--border-ui);
            padding-bottom: 6px;
            font-weight: 700;
        }
        .spell-stack {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .card {
            background-color: var(--bg-panel);
            border: 1px solid var(--border-ui);
            padding: 12px;
            border-radius: 4px;
            cursor: pointer;
            position: relative;
            transition: border-color 0.15s ease, transform 0.1s ease;
        }
        .card:hover { border-color: #565451; transform: translateY(-1px); }
        .card.used {
            opacity: 0.2;
            pointer-events: none;
            filter: grayscale(100%);
        }
        .card-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        .card-title { font-weight: 600; color: var(--text-light); font-size: 0.95rem; }
        .card-rarity { font-size: 0.65rem; text-transform: uppercase; color: var(--gold); font-weight: bold; background: rgba(223,177,91,0.1); padding: 2px 5px; border-radius: 2px; }
        .card-effect { font-size: 0.8rem; color: var(--text-main); line-height: 1.3; }

        /* Center Column: Chessboard & Tags */
        .panel-center {
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .player-tag {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 4px;
            font-size: 0.95rem;
            color: var(--text-light);
        }
        .player-info { display: flex; align-items: center; gap: 8px; font-weight: 500; }
        .badge-status { font-size: 0.75rem; background: var(--bg-panel); border: 1px solid var(--border-ui); padding: 2px 6px; border-radius: 10px; color: var(--text-main); }
        .badge-status.active-turn { background: var(--accent-green); color: #fff; border-color: var(--accent-green); }

        .board-wrapper {
            background-color: var(--bg-panel);
            padding: 4px;
            border-radius: 3px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            transition: box-shadow 0.3s ease;
        }
        .board-wrapper.magic-glow {
            box-shadow: 0 0 30px var(--magic-glow);
            border: 1px solid blueviolet;
        }
        #board { width: 100%; }

        /* Right Column: Game Status, Live Moves & Settings Override */
        .panel-right {
            background-color: var(--bg-panel);
            border: 1px solid var(--border-ui);
            border-radius: 4px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-header {
            background-color: var(--bg-darker);
            padding: 12px 16px;
            font-size: 0.85rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-ui);
        }
        .move-history-table {
            flex: 1;
            padding: 14px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.9rem;
            line-height: 1.5;
            display: grid;
            grid-template-columns: 40px 1fr 1fr;
            align-content: start;
            gap: 4px 10px;
        }
        .move-num { color: #565451; text-align: right; }
        .move-ply { color: var(--text-light); cursor: pointer; }
        .move-ply:hover { background: #363431; }

        .sidebar-footer {
            background-color: var(--bg-darker);
            padding: 10px 16px;
            border-top: 1px solid var(--border-ui);
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.8rem;
        }
        
        /* Legal Move Markers (Modern Translucent Core) */
        .legal-dot { position: relative; }
        .legal-dot::after {
            content: ''; position: absolute; top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 24%; height: 24%;
            background-color: rgba(0, 0, 0, 0.15);
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%; pointer-events: none;
        }
        
        /* Overlay Alerts */
        #floating-alert {
            position: fixed; top: 25px; right: 25px;
            background: #262421; border-left: 4px solid var(--gold);
            padding: 14px 24px; border-radius: 3px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            font-size: 0.95rem; font-weight: 500; color: #fff; display: none; z-index: 1000;
        }
    </style>
</head>
<body>

    <div id="invite-banner">
        <span>Invite link:</span>
        <input type="text" id="shareLink" readonly>
        <button class="btn-action" onclick="copyLink()">Copy</button>
    </div>

    <div id="floating-alert"></div>

    <div class="app-container">
        
        <div class="panel-left">
            <div class="panel-title">Spells Inventory</div>
            <div id="spells-view" class="spell-stack"></div>
        </div>

        <div class="panel-center">
            <div class="player-tag">
                <div class="player-info">
                    <span id="opp-name">Opponent</span>
                </div>
                <div id="opp-status-badge" class="badge-status">Connecting</div>
            </div>

            <div class="board-wrapper" id="board-wrap">
                <div id="board"></div>
            </div>

            <div class="player-tag">
                <div class="player-info">
                    <span id="my-name">You</span>
                </div>
                <div id="my-status-badge" class="badge-status active-turn">Your Turn</div>
            </div>
        </div>

        <div class="panel-right">
            <div class="sidebar-header">Live Evaluation Log</div>
            <div id="move-grid" class="move-history-table"></div>
            
            <div class="sidebar-footer">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <input type="checkbox" id="magicModeToggle" style="accent-color: blueviolet;">
                    <label for="magicModeToggle" style="cursor:pointer; color:#7a7875;">Spell Override Engine</label>
                </div>
                <span id="match-status-text" style="color: var(--accent-green); font-weight:600;">Active</span>
            </div>
        </div>

    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>

    <script>
        // CLEAN AUDIO STREAMS FROM CHESS ASSET SERVERS
        const audioMove = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3');
        const audioCapture = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3');
        const audioCheck = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-check.mp3');
        const audioCastle = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/castle.mp3');
        const audioChime = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3'); 

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
            document.querySelector('.btn-action').innerText = "Copied";
            setTimeout(() => document.querySelector('.btn-action').innerText = "Copy", 2000);
        }

        const p1Spells = [
            { id: 's1', name: "Avada Kedavra", rarity: "Legendary", effect: "Instantly banish targeted enemy piece from play." },
            { id: 's2', name: "Imperio", rarity: "Rare", effect: "Commandeer an opponent piece to perform a legal shift." },
            { id: 's3', name: "Accio", rarity: "Common", effect: "Pull a friendly asset up to 2 units in any vector." }
        ];
        const p2Spells = [
            { id: 's1', name: "Time-Turner", rarity: "Legendary", effect: "Rewind spatial coordinate configurations." },
            { id: 's2', name: "Sectumsempra", rarity: "Rare", effect: "Bind an opponent target, disabling motion for two rounds." },
            { id: 's3', name: "Wingardium Leviosa", rarity: "Common", effect: "Float an asset to any adjacent vector block." }
        ];

        let currentMoveNumber = 1;
        function updateUIMoveTable(from, to, color) {
            if (color === 'w') {
                $('#move-grid').append(`<div class="move-num">${currentMoveNumber}.</div>`);
                $('#move-grid').append(`<div class="move-ply">${from}→${to}</div>`);
            } else {
                $('#move-grid').append(`<div class="move-ply">${from}→${to}</div>`);
                currentMoveNumber++;
            }
            $('#move-grid').scrollTop($('#move-grid')[0].scrollHeight);
        }

        function triggerPopup(msg) {
            const $alert = $('#floating-alert');
            $alert.html(msg).fadeIn(150);
            setTimeout(() => $alert.fadeOut(300), 3000);
        }

        let board = null;
        let game = new Chess();
        let myColor = null;

        socket.on('role_assigned', (color) => {
            myColor = color;
            let currentPool = (color === 'w') ? p1Spells : p2Spells;
            
            currentPool.forEach(s => {
                const card = $(`
                    <div class="card" id="${s.id}">
                        <div class="card-header-row">
                            <span class="card-title">${s.name}</span>
                            <span class="card-rarity">${s.rarity}</span>
                        </div>
                        <div class="card-effect">${s.effect}</div>
                    </div>
                `);
                
                card.on('click', function() {
                    if(!$(this).hasClass('used')) {
                        $(this).addClass('used');
                        audioChime.play();
                        
                        socket.emit('spell_cast', { name: s.name });
                        triggerPopup(`⚡ Cast: ${s.name.toUpperCase()}`);
                        
                        $('#board-wrap').addClass('magic-glow');
                        $('#magicModeToggle').prop('checked', true);
                    }
                });
                $('#spells-view').append(card);
            });

            if (myColor === 'b') {
                board.orientation('black');
                $('#my-name').text('Player 2 (Black)');
                $('#opp-name').text('Player 1 (White)');
            } else {
                $('#my-name').text('Player 1 (White)');
                $('#opp-name').text('Player 2 (Black)');
            }
            syncTurnIndicatorBadges();
        });

        socket.on('user_joined', () => {
            $('#invite-banner').css('opacity', '0');
            setTimeout(() => $('#invite-banner').hide(), 300);
            
            audioCastle.play();
            $('#opp-status-badge').text('Ready');
            triggerPopup('Match Engaged. Player 2 Linked.');
        });

        socket.on('standard_move', (move) => {
            let res = game.move(move);
            board.position(game.fen());
            
            if (game.in_check()) audioCheck.play();
            elif (res && res.captured) audioCapture.play();
            else audioMove.play();
            
            updateUIMoveTable(move.from, move.to, game.turn() === 'b' ? 'w' : 'b');
            syncTurnIndicatorBadges();
        });

        socket.on('magic_sync', (fenState) => {
            game.load(fenState + " w - - 0 1");
            board.position(fenState);
            audioChime.play();
            syncTurnIndicatorBadges();
        });

        socket.on('spell_cast', (spellData) => {
            audioChime.play();
            triggerPopup(`✨ Opponent cast ${spellData.name.toUpperCase()}`);
        });

        function syncTurnIndicatorBadges() {
            if(!myColor) return;
            const activeColor = game.turn();
            if (activeColor === myColor) {
                $('#my-status-badge').addClass('active-turn').text('Your Turn');
                $('#opp-status-badge').removeClass('active-turn').text('Waiting');
            } else {
                $('#opp-status-badge').addClass('active-turn').text('Thinking');
                $('#my-status-badge').removeClass('active-turn').text('Wait');
            }
            if (game.in_checkmate()) {
                $('#match-status-text').text('Checkmate - End').css('color', '#ff4c4c');
            }
        }

        // VISUAL LEGAL INTERFACE MARKERS
        function clearDots () { $('#board .square-55d63').removeClass('legal-dot'); }
        function drawDot (square) { $('#board .square-' + square).addClass('legal-dot'); }

        function onMouseoverSquare (square, piece) {
            if ($('#magicModeToggle').is(':checked') || game.game_over()) return;
            if (game.turn() !== myColor) return;
            if (piece && piece.charAt(0) !== myColor) return;

            var moves = game.moves({ square: square, verbose: true });
            if (moves.length === 0) return;

            for (var i = 0; i < moves.length; i++) { drawDot(moves[i].to); }
        }

        function onMouseoutSquare (square, piece) { clearDots(); }

        function onDragStart(source, piece) {
            if ($('#magicModeToggle').is(':checked')) return true;
            if (game.game_over() || game.turn() !== myColor) return false;
            if ((myColor === 'w' && piece.search(/^b/) !== -1) || (myColor === 'b' && piece.search(/^w/) !== -1)) return false;
        }

        function onDrop(source, target) {
            clearDots();
            
            if ($('#magicModeToggle').is(':checked')) {
                if (source === target) return 'snapback';
                
                audioChime.play();
                $('#board-wrap').removeClass('magic-glow');
                $('#magicModeToggle').prop('checked', false);

                setTimeout(() => {
                    const nextFen = board.fen();
                    game.load(nextFen + " w - - 0 1");
                    socket.emit('magic_sync', nextFen);
                }, 100);
                return;
            }

            let move = game.move({ from: source, to: target, promotion: 'q' });
            if (move === null) return 'snapback';
            
            updateUIMoveTable(source, target, myColor);

            if (game.in_check()) audioCheck.play();
            elif (move.captured) audioCapture.play();
            else audioMove.play();

            socket.emit('standard_move', { from: source, to: target, promotion: 'q' });
            syncTurnIndicatorBadges();
        }

        function onSnapEnd() {
            if(!$('#magicModeToggle').is(':checked')) board.position(game.fen());
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
    print(f"> PRODUCTION SYSTEM RUNNING. LOCAL PORT: {port}")
    socketio.run(app, host='0.0.0.0', port=port)
