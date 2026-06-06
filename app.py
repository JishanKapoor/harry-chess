import os
from flask import Flask
from flask_socketio import SocketIO, join_room, emit
from flask import request

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lumos_maxima_secret'

# Removed eventlet. It will now auto-default to modern threading + simple-websocket
socketio = SocketIO(app, cors_allowed_origins="*")

client_rooms = {}
room_counts = {}

# STRICT LOGGING PROTOCOL: Console logs only. No Excel/CRM.
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
    emit('user_joined', room=room_id, include_self=False)

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

# ==========================================
# THE WIZARD'S CHESS UI (HTML/JS/CSS)
# ==========================================
HTML_PAYLOAD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wizard's Chess Multiplayer</title>
    
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Spectral:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
    
    <style>
        :root { --bg-color: #0f1115; --gold: #d4af37; --parchment: #f4e8c1; --dark-parchment: #d9c28e; }
        body { font-family: 'Spectral', serif; background-color: var(--bg-color); background-image: radial-gradient(circle at center, #1f2229 0%, #08090b 100%); color: var(--parchment); display: flex; flex-direction: column; align-items: center; margin: 0; padding: 20px; min-height: 100vh; }
        h1 { font-family: 'Cinzel', serif; color: var(--gold); text-shadow: 0 0 10px rgba(212, 175, 55, 0.5); margin-bottom: 5px; font-size: 2.5rem; }
        
        /* Chess.com style Share Lobby */
        .share-container { background: #1a1c23; padding: 15px 25px; border: 2px solid var(--gold); border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; gap: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .share-text { font-family: 'Cinzel', serif; font-weight: bold; font-size: 1.1rem; }
        .share-container input { width: 300px; padding: 8px; background: #0f1115; color: #fff; border: 1px solid #555; border-radius: 4px; font-family: monospace; }
        .copy-btn { background: var(--gold); color: #000; border: none; padding: 8px 15px; font-family: 'Cinzel', serif; font-weight: bold; cursor: pointer; border-radius: 4px; transition: 0.2s; }
        .copy-btn:hover { background: #f1d570; box-shadow: 0 0 10px var(--gold); }
        
        .layout { display: flex; gap: 30px; max-width: 1200px; width: 100%; justify-content: center; align-items: flex-start; }
        .column { display: flex; flex-direction: column; gap: 15px; }
        .board-container { background-color: #2a2a2a; padding: 10px; border: 4px solid var(--gold); border-radius: 5px; box-shadow: 0 0 30px rgba(0, 0, 0, 0.8); }
        #board { width: 450px; }
        .controls { display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.5); padding: 10px; border: 1px solid var(--gold); }
        .magic-toggle { display: flex; align-items: center; gap: 10px; font-family: 'Cinzel', serif; color: #ff4c4c; font-weight: bold; }
        input[type="checkbox"] { accent-color: #ff4c4c; width: 18px; height: 18px; cursor: pointer; }
        
        /* Personalized Hands */
        .hand { display: flex; flex-direction: column; gap: 10px; width: 280px; transition: 0.3s; }
        .hand.disabled-hand { opacity: 0.3; pointer-events: none; filter: grayscale(100%); }
        .hand-title { font-family: 'Cinzel', serif; font-size: 1.2rem; text-align: center; border-bottom: 1px solid var(--gold); padding-bottom: 5px; }
        
        /* Magic Spells */
        .card { background: var(--dark-parchment); color: #111; padding: 10px; border-radius: 5px; border: 2px solid #555; cursor: pointer; position: relative; transition: transform 0.1s; }
        .card:hover { transform: scale(1.03); }
        .card.used { opacity: 0.4; pointer-events: none; text-decoration: line-through; filter: grayscale(100%); }
        .card-title { font-family: 'Cinzel', serif; font-weight: bold; font-size: 1rem; margin-bottom: 5px; }
        .card-effect { font-size: 0.85rem; line-height: 1.2; }
        .card.legendary { border-color: #b8860b; background: linear-gradient(135deg, #f4e8c1, #ffd700); }
        .card.rare { border-color: #4b0082; background: linear-gradient(135deg, #f4e8c1, #dda0dd); }
        .card.common { border-color: #555; background: linear-gradient(135deg, #f4e8c1, #cccccc); }
        .rarity-tag { position: absolute; top: 5px; right: 5px; font-size: 0.65rem; text-transform: uppercase; font-weight: bold; opacity: 0.7; }
        
        /* Legal Move Highlights (Gold Dot) */
        .legal-highlight { position: relative; }
        .legal-highlight::after {
            content: ''; position: absolute; top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 30%; height: 30%;
            background-color: rgba(212, 175, 55, 0.8);
            border-radius: 50%; box-shadow: 0 0 10px var(--gold);
            pointer-events: none;
        }

        .log-container { width: 100%; max-width: 1100px; background: #111; border: 1px solid #444; margin-top: 20px; padding: 15px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 0.9rem; color: #00ff00; }
        .log-entry.spell { color: #ff00ff; }
        .log-entry.magic-move { color: #ffaa00; }
    </style>
</head>
<body>

    <h1>Wizard's Chess</h1>
    
    <div class="share-container">
        <span class="share-text">Invite Player 2:</span>
        <input type="text" id="shareLink" readonly>
        <button class="copy-btn" onclick="copyLink()">Copy Link</button>
    </div>

    <div class="layout">
        <div class="column">
            <div class="hand" id="hand-p1">
                <div class="hand-title" id="title-p1">Player 1 Spells (White)</div>
            </div>
        </div>

        <div class="column">
            <div class="board-container"><div id="board"></div></div>
            <div class="controls">
                <div id="status" style="font-family: 'Cinzel', serif; color: #4CAF50; font-size: 1.1rem;">Waiting for server...</div>
                <div class="magic-toggle">
                    <input type="checkbox" id="magicModeToggle">
                    <label for="magicModeToggle">Cast Spell / Free Move</label>
                </div>
            </div>
        </div>

        <div class="column">
            <div class="hand" id="hand-p2">
                <div class="hand-title" id="title-p2">Player 2 Spells (Black)</div>
            </div>
        </div>
    </div>

    <div class="log-container" id="actionLogger">
        <div style="color:#888; margin-bottom: 10px;">> SESSION INITIATED. WAITING FOR OPPONENT.</div>
    </div>

    <!-- WebSockets and Chess JS -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>

    <script>
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
            document.querySelector('.copy-btn').innerText = "Copied!";
            setTimeout(() => document.querySelector('.copy-btn').innerText = "Copy Link", 2000);
        }

        const p1Spells = [
            { id: 'p1_1', name: "Avada Kedavra", rarity: "legendary", effect: "Target enemy piece is instantly destroyed." },
            { id: 'p1_2', name: "Imperio", rarity: "rare", effect: "Force one enemy piece to make a legal move chosen by you." },
            { id: 'p1_3', name: "Expecto Patronum", rarity: "rare", effect: "Shields an area." },
            { id: 'p1_4', name: "Protego", rarity: "common", effect: "One of your pieces cannot be captured until your next turn." },
            { id: 'p1_5', name: "Accio", rarity: "common", effect: "Move one of your pieces up to 2 squares in any direction." },
            { id: 'p1_6', name: "Expelliarmus", rarity: "common", effect: "Target enemy piece skips its next turn." }
        ];

        const p2Spells = [
            { id: 'p2_1', name: "Time-Turner", rarity: "legendary", effect: "Revert the board to a previous state." },
            { id: 'p2_2', name: "Fiendfyre", rarity: "rare", effect: "Destroys multiple pieces." },
            { id: 'p2_3', name: "Sectumsempra", rarity: "rare", effect: "Target enemy piece cannot move for two turns." },
            { id: 'p2_4', name: "Wingardium Leviosa", rarity: "common", effect: "Move one of your pieces to any adjacent empty square." },
            { id: 'p2_5', name: "Alohomora", rarity: "common", effect: "One chosen piece may move through occupied friendly pieces." },
            { id: 'p2_6', name: "Protego", rarity: "common", effect: "One of your pieces cannot be captured until your next turn." }
        ];

        function keepProperLogs(text, type = 'standard') {
            const time = new Date().toLocaleTimeString();
            let css = 'log-entry';
            if (type === 'spell') css += ' spell';
            if (type === 'magic') css += ' magic-move';
            $('#actionLogger').append(`<div class="${css}">[${time}] ${text}</div>`);
            $('#actionLogger').scrollTop($('#actionLogger')[0].scrollHeight);
        }

        function renderCards(spells, containerId) {
            spells.forEach(spell => {
                const card = $(`<div class="card ${spell.rarity}" id="${spell.id}">
                    <div class="rarity-tag">${spell.rarity}</div>
                    <div class="card-title">${spell.name}</div>
                    <div class="card-effect">${spell.effect}</div>
                </div>`);
                
                card.on('click', function() {
                    if(!$(this).hasClass('used')) {
                        $(this).addClass('used');
                        keepProperLogs(`You cast ${spell.name.toUpperCase()}!`, 'spell');
                        socket.emit('spell_cast', { id: spell.id, name: spell.name });
                    }
                });
                $(`#${containerId}`).append(card);
            });
        }
        renderCards(p1Spells, 'hand-p1');
        renderCards(p2Spells, 'hand-p2');

        let board = null;
        let game = new Chess();
        let myColor = null;

        socket.on('role_assigned', (color) => {
            myColor = color;
            if (myColor === 'w') {
                $('#title-p1').html("<b>Your Spells</b> (White)");
                $('#hand-p2').addClass('disabled-hand');
            } else {
                board.orientation('black');
                $('#title-p2').html("<b>Your Spells</b> (Black)");
                $('#hand-p1').addClass('disabled-hand');
            }
            updateStatus();
        });

        socket.on('user_joined', () => { keepProperLogs('Player 2 has joined the lobby! Game ON.', 'magic'); });

        socket.on('standard_move', (move) => {
            game.move(move);
            board.position(game.fen());
            keepProperLogs(`Opponent moved from ${move.from} to ${move.to}.`);
            updateStatus();
        });

        socket.on('magic_sync', (fenState) => {
            game.load(fenState + " w - - 0 1");
            board.position(fenState);
            keepProperLogs(`Opponent triggered a Magical Board Alteration!`, 'magic');
            updateStatus();
        });

        socket.on('spell_cast', (spellData) => {
            $(`#${spellData.id}`).addClass('used');
            keepProperLogs(`Opponent cast ${spellData.name.toUpperCase()}!`, 'spell');
        });

        function removeGreySquares () { $('#board .square-55d63').removeClass('legal-highlight'); }
        function greySquare (square) { $('#board .square-' + square).addClass('legal-highlight'); }

        function onMouseoverSquare (square, piece) {
            if ($('#magicModeToggle').is(':checked') || game.game_over()) return;
            if (game.turn() !== myColor) return;
            if (piece && piece.charAt(0) !== myColor) return;

            var moves = game.moves({ square: square, verbose: true });
            if (moves.length === 0) return;

            greySquare(square); 
            for (var i = 0; i < moves.length; i++) { greySquare(moves[i].to); }
        }

        function onMouseoutSquare (square, piece) { removeGreySquares(); }

        function onDragStart(source, piece) {
            if ($('#magicModeToggle').is(':checked')) return true;
            if (game.game_over()) return false;
            if (game.turn() !== myColor) return false;
            if ((myColor === 'w' && piece.search(/^b/) !== -1) ||
                (myColor === 'b' && piece.search(/^w/) !== -1)) return false;
        }

        function onDrop(source, target) {
            removeGreySquares();
            
            if ($('#magicModeToggle').is(':checked')) {
                if (source === target) return 'snapback';
                if (target === 'offboard') keepProperLogs(`Magical Alteration: Piece destroyed!`, 'magic');
                else keepProperLogs(`Magical Alteration: Piece moved to ${target}.`, 'magic');
                
                setTimeout(() => {
                    const newFen = board.fen();
                    game.load(newFen + " w - - 0 1");
                    socket.emit('magic_sync', newFen);
                }, 100);
                return;
            }

            let move = game.move({ from: source, to: target, promotion: 'q' });
            if (move === null) return 'snapback';

            keepProperLogs(`You moved ${source} to ${target}.`);
            socket.emit('standard_move', { from: source, to: target, promotion: 'q' });
            updateStatus();
        }

        function onSnapEnd() {
            if(!$('#magicModeToggle').is(':checked')) board.position(game.fen());
        }

        function updateStatus() {
            if(!myColor) return;
            let statusHTML = (game.turn() === 'w') ? 'White to move' : 'Black to move';
            if (game.turn() === myColor) statusHTML = "<b>Your turn</b>";
            if (game.in_checkmate()) statusHTML = 'Game over, checkmate.';
            $('#status').html(statusHTML);
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
