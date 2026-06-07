import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "wizard_chess_secret_v4")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Custom SVG Artwork for Spells
SVG_TIME = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="45" fill="none" stroke="#eab308" stroke-width="3" stroke-dasharray="10 5"/><circle cx="50" cy="50" r="38" fill="none" stroke="#eab308" stroke-width="2"/><path d="M40 30 L60 30 L50 50 Z" fill="#fef08a"/><path d="M40 70 L60 70 L50 50 Z" fill="#ca8a04"/><path d="M35 25 L65 25 M35 75 L65 75" stroke="#eab308" stroke-width="4" stroke-linecap="round"/><circle cx="50" cy="50" r="8" fill="#fef08a"/></svg>'''
SVG_AVADA = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M80 20 L40 50 L55 60 L20 90" stroke="#22c55e" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round" filter="drop-shadow(0 0 8px #22c55e)"/><circle cx="30" cy="30" r="15" fill="none" stroke="#4ade80" stroke-width="2"/><path d="M25 25 Q30 20 35 25 M25 35 Q30 40 35 35" stroke="#4ade80" stroke-width="2" fill="none"/></svg>'''
SVG_IMPERIO = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M10 50 Q50 10 90 50 Q50 90 10 50 Z" fill="none" stroke="#ec4899" stroke-width="4"/><circle cx="50" cy="50" r="15" fill="#f472b6" filter="drop-shadow(0 0 10px #ec4899)"/><circle cx="50" cy="50" r="5" fill="#831843"/><path d="M50 65 L40 90 M50 65 L50 95 M50 65 L60 90" stroke="#fbcfe8" stroke-width="2" stroke-dasharray="4 4"/></svg>'''
SVG_SECTUM = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M20 20 L80 80 M30 10 L90 70 M10 30 L70 90" stroke="#d1d5db" stroke-width="4" stroke-linecap="round"/><path d="M50 50 Q60 70 50 80 Q40 70 50 50 Z" fill="#ef4444" filter="drop-shadow(0 0 5px #ef4444)"/><path d="M70 30 Q75 45 70 50 Q65 45 70 30 Z" fill="#ef4444"/></svg>'''
SVG_FIENDFYRE = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M50 90 Q20 90 30 60 Q40 30 50 10 Q60 30 70 60 Q80 90 50 90 Z" fill="#ea580c"/><path d="M50 85 Q30 85 38 65 Q45 45 50 25 Q55 45 62 65 Q70 85 50 85 Z" fill="#fb923c"/><path d="M50 75 Q40 75 44 60 Q48 45 50 35 Q52 45 56 60 Q60 75 50 75 Z" fill="#fef08a"/><circle cx="42" cy="55" r="3" fill="#7c2d12"/><circle cx="58" cy="55" r="3" fill="#7c2d12"/></svg>'''
SVG_ACCIO = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M80 80 L30 30" stroke="#78350f" stroke-width="8" stroke-linecap="round"/><path d="M30 30 L20 20" stroke="#fcd34d" stroke-width="6" stroke-linecap="round"/><path d="M20 20 Q40 5 60 20 M30 30 Q50 15 70 30 M40 40 Q60 25 80 40" fill="none" stroke="#38bdf8" stroke-width="3" stroke-dasharray="6 4" filter="drop-shadow(0 0 5px #38bdf8)"/></svg>'''

SPELLS = [
    {"id": "time", "name": "Time-Turner", "type": "instant", "desc": "Reverse opponent's last spell or move.", "color": "#eab308", "image": SVG_TIME},
    {"id": "avada", "name": "Avada Kedavra", "type": "enemy", "desc": "Destroy an enemy piece instantly.", "color": "#22c55e", "image": SVG_AVADA},
    {"id": "imperio", "name": "Imperio", "type": "drag_enemy", "desc": "Command an enemy piece to move.", "color": "#ec4899", "image": SVG_IMPERIO},
    {"id": "sectum", "name": "Sectumsempra", "type": "enemy", "desc": "Demote an enemy piece to a Pawn.", "color": "#ef4444", "image": SVG_SECTUM},
    {"id": "fiendfyre", "name": "Fiendfyre", "type": "any", "desc": "Incinerate a 3x3 square area.", "color": "#f97316", "image": SVG_FIENDFYRE},
    {"id": "accio", "name": "Accio", "type": "drag_own", "desc": "Summon your piece up to 2 squares.", "color": "#0ea5e9", "image": SVG_ACCIO},
]

ROOMS = {}

def fen_side_to_move(fen: str) -> str:
    try:
        return fen.split()[1]
    except Exception:
        return "w"

def fresh_hand():
    # Both players get the exact same 6 spells. Each can only be used once.
    return list(SPELLS)

def get_room(room_id: str):
    if room_id not in ROOMS:
        ROOMS[room_id] = {
            "fen": START_FEN,
            "turn": "w",
            "history": [START_FEN],
            "player_ids": {"w": None, "b": None},
            "player_names": {"w": "White", "b": "Black"},
            "hands": {"w": None, "b": None},
            "used": {"w": set(), "b": set()},
            "game_over": False,
            "winner": None,
            "last_action": None,
        }
    return ROOMS[room_id]

def room_snapshot(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        return {}
    return {
        "room": room_id,
        "fen": room["fen"],
        "turn": room["turn"],
        "started": room["player_ids"]["w"] is not None and room["player_ids"]["b"] is not None,
        "game_over": room["game_over"],
        "winner": room["winner"],
        "players": room["player_names"],
        "history_len": len(room["history"]),
    }

def player_color(room, player_id):
    if room["player_ids"]["w"] == player_id:
        return "w"
    if room["player_ids"]["b"] == player_id:
        return "b"
    return None

@app.route("/")
def index():
    return render_template_string(HTML_PAYLOAD)

@socketio.on("join_room")
def handle_join(data):
    room_id = data.get("room")
    player_id = data.get("player_id")
    player_name = (data.get("player_name") or "").strip()[:24] or "Player"

    if not room_id or not player_id:
        return

    room = get_room(room_id)
    color = player_color(room, player_id)

    if color is None:
        if room["player_ids"]["w"] is None:
            color = "w"
            room["player_ids"]["w"] = player_id
            room["player_names"]["w"] = player_name
        elif room["player_ids"]["b"] is None:
            color = "b"
            room["player_ids"]["b"] = player_id
            room["player_names"]["b"] = player_name
        else:
            color = "s"

    join_room(room_id)

    if color in ("w", "b") and room["hands"][color] is None:
        room["hands"][color] = fresh_hand()

    emit("role_assigned", {
        "color": color,
        "hand": room["hands"].get(color, []) if color in ("w", "b") else [],
        "used": list(room["used"].get(color, set())) if color in ("w", "b") else [],
        "snapshot": room_snapshot(room_id),
    }, to=request.sid)

    emit("room_state", room_snapshot(room_id), to=room_id)

@socketio.on("standard_move")
def handle_standard_move(data):
    room_id = data.get("room")
    player_id = data.get("player_id")
    fen = data.get("fen")

    room = ROOMS.get(room_id)
    if not room or room["game_over"]:
        return

    color = player_color(room, player_id)
    if color is None or room["turn"] != color or not fen:
        return

    room["fen"] = fen
    room["turn"] = fen_side_to_move(fen)
    room["history"].append(fen)
    room["last_action"] = {
        "type": "move",
        "color": color,
        "san": data.get("san") or "",
        "from": data.get("from"),
        "to": data.get("to"),
    }

    emit("board_update", {
        "fen": room["fen"],
        "san": data.get("san") or "",
        "color": color,
        "turn": room["turn"],
        "is_spell": False,
        "room_state": room_snapshot(room_id),
    }, to=room_id)

@socketio.on("spell_effect")
def handle_spell_effect(data):
    room_id = data.get("room")
    player_id = data.get("player_id")
    spell_id = data.get("spell_id")
    fen = data.get("fen")

    room = ROOMS.get(room_id)
    if not room or room["game_over"] or not spell_id:
        return

    color = player_color(room, player_id)
    if color is None or room["turn"] != color:
        return
    if spell_id in room["used"][color]:
        return

    log_text = (data.get("log") or spell_id).strip()

    # Special Logic for Time-Turner: Reverts Board State and Turns
    if spell_id == "time":
        if len(room["history"]) < 2:
            return # Cannot rewind at turn 1
        room["history"].pop() # Pop the current board state
        fen = room["history"][-1] # Grabs the previous board state
        log_text = "TIME-TURNER (Reversed Action)"
    else:
        if not fen:
            return

        # FORCE TURN SWAP for all standard spells to end turn officially
        next_turn = "b" if color == "w" else "w"
        room["turn"] = next_turn

        parts = fen.split(" ")
        if len(parts) > 1:
            parts[1] = next_turn
        if len(parts) > 3:
            parts[3] = "-"
        if color == "b" and len(parts) > 5:
            try:
                parts[5] = str(int(parts[5]) + 1)
            except:
                pass
        fen = " ".join(parts)

    room["used"][color].add(spell_id)
    room["fen"] = fen
    
    # If it was a Time-Turner, the turn correctly swaps back to the person who was reversed.
    if spell_id == "time":
        room["turn"] = fen_side_to_move(fen)
        
    room["last_action"] = {
        "type": "spell",
        "color": color,
        "spell_id": spell_id,
        "log": log_text,
    }
    
    # Time-Turner action is NOT saved to history, to allow for clean undo states
    if spell_id != "time":
        room["history"].append(fen)

    emit("board_update", {
        "fen": room["fen"],
        "spell_id": spell_id,
        "san": log_text,
        "color": color,
        "turn": room["turn"],
        "is_spell": True,
        "used_spell_id": spell_id,
        "room_state": room_snapshot(room_id),
    }, to=room_id)

@socketio.on("resign")
def handle_resign(data):
    room_id = data.get("room")
    player_id = data.get("player_id")

    room = ROOMS.get(room_id)
    if not room or room["game_over"]:
        return

    color = player_color(room, player_id)
    if color is None:
        return

    room["game_over"] = True
    room["winner"] = "b" if color == "w" else "w"
    room["last_action"] = {"type": "resign", "color": color}

    emit("game_over", {
        "winner": room["winner"],
        "winner_name": room["player_names"].get(room["winner"], "Opponent"),
        "resigned_color": color,
        "room_state": room_snapshot(room_id),
    }, to=room_id)

HTML_PAYLOAD = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Wizard's Chess</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Cinzel:wght@600;800&display=swap');

        :root {
            --bg: #0d0b13;
            --panel: #1a1523;
            --panel-2: #16121c;
            --line: #3c314a;
            --muted: #8b7d9b;
            --green: #81b64c;
            --light: #ebecd0;
            --dark: #739552;
        }

        * { box-sizing: border-box; }
        
        /* Removed overflow hidden to allow native scrolling on all devices */
        body {
            margin: 0;
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            background-image: radial-gradient(circle at 50% 50%, #171221 0%, #0d0b13 100%);
            color: #fff;
        }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: #4a3b5c; border-radius: 999px; }

        .text-muted { color: var(--muted); }

        .sq-light { background: var(--light); }
        .sq-dark { background: var(--dark); }

        .board-shell {
            width: 100%;
            aspect-ratio: 1 / 1;
            position: relative;
            border-radius: 8px;
            overflow: hidden;
            border: 4px solid var(--panel);
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
            transition: transform 0.18s ease;
            background: #000;
        }

        .board-shell.flipped {
            transform: rotate(180deg);
        }

        .square {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            user-select: none;
            -webkit-user-drag: none;
        }

        .piece {
            width: 100%;
            height: 100%;
            position: relative;
            z-index: 10;
            background-size: contain;
            background-position: center;
            background-repeat: no-repeat;
            transition: transform 0.05s ease;
            user-select: none;
            -webkit-user-drag: none;
        }

        .board-shell.flipped .piece {
            transform: rotate(180deg);
        }

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

        .sq-selected {
            position: absolute;
            inset: 0;
            background: rgba(20, 85, 30, 0.5);
            pointer-events: none;
        }

        .sq-highlight {
            position: absolute;
            inset: 0;
            background: rgba(255, 255, 51, 0.35);
            pointer-events: none;
        }

        .move-dot {
            width: 32%;
            height: 32%;
            border-radius: 50%;
            background: rgba(0,0,0,0.25);
            position: absolute;
            pointer-events: none;
        }

        .capture-dot {
            width: 85%;
            height: 85%;
            border-radius: 50%;
            border: 6px solid rgba(0,0,0,0.25);
            background: transparent;
            position: absolute;
            pointer-events: none;
        }

        /* Magical UI Enhancements */
        .grimoire-container {
            background-color: var(--panel-2);
            background-image: radial-gradient(circle at center, rgba(30,25,40,0.8), rgba(15,10,20,1));
            border-left: 1px solid #4a3b5c;
            box-shadow: -10px 0 30px rgba(0,0,0,0.8);
            position: relative;
        }
        
        .grimoire-container::before {
            content: '';
            position: absolute;
            inset: 0;
            background: url('https://www.transparenttextures.com/patterns/cream-paper.png');
            opacity: 0.05;
            pointer-events: none;
        }

        .spell-card {
            background: linear-gradient(145deg, #241d2e 0%, #15111b 100%);
            border: 2px solid #3c314a;
            position: relative;
            overflow: hidden;
            transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
            border-radius: 12px;
        }

        .spell-card::after {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: 10px;
            box-shadow: inset 0 0 15px rgba(0,0,0,0.8);
            pointer-events: none;
        }

        .spell-card:hover:not(.used) {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 0 15px 25px -5px rgba(0,0,0,0.6), 0 0 15px var(--spell-glow);
            border-color: var(--spell-color);
            z-index: 10;
        }

        .spell-card.active {
            transform: translateY(-4px);
            box-shadow: 0 0 20px var(--spell-glow), inset 0 0 15px var(--spell-glow);
            border-color: var(--spell-color);
            z-index: 10;
        }

        .spell-card.used {
            opacity: 0.35;
            filter: grayscale(1) brightness(0.6);
            pointer-events: none; /* Physically prevents secondary clicks */
        }

        .overlay {
            position: absolute;
            inset: 0;
            background: rgba(0,0,0,0.75);
            backdrop-filter: blur(5px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 50;
        }

        .game-root {
            min-height: 100vh;
            width: 100%;
        }

        .shell-left {
            min-height: 0;
        }

        .board-holder {
            width: 100%;
            max-width: min(100%, 85vh);
            margin: 0 auto;
        }

        #move-history {
            background: rgba(0,0,0,0.3);
            color: #d1c5e0;
        }
    </style>
</head>
<body>
<div class="game-root flex flex-col lg:flex-row">
    <div class="flex-1 flex flex-col justify-center p-2 lg:p-4 shell-left">
        <div class="board-holder space-y-2 lg:space-y-3">
            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 bg-black rounded flex items-center justify-center overflow-hidden border border-[var(--line)] shrink-0 shadow-lg">
                        <img src="https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png" class="w-8 h-8 object-contain drop-shadow" id="opp-avatar">
                    </div>
                    <div class="min-w-0">
                        <div class="font-bold text-sm tracking-wide truncate" id="opp-name">Opponent</div>
                        <div class="flex items-center mt-0.5 min-h-[18px] flex-wrap gap-1" id="captured-top"></div>
                    </div>
                </div>
                <div class="text-xs font-mono font-bold bg-[var(--panel)] text-[var(--muted)] px-3 py-2 rounded shrink-0 shadow border border-[var(--line)]" id="opp-status">Waiting</div>
            </div>

            <div class="board-shell" id="board-shell">
                <div id="board" class="w-full h-full grid grid-cols-8 grid-rows-8 select-none"></div>

                <div id="waiting-overlay" class="overlay">
                    <div class="bg-[var(--panel)] border border-[var(--line)] p-6 rounded-2xl text-center max-w-[92%] shadow-2xl w-[420px]">
                        <h2 class="text-xl font-bold mb-2 text-white">
                            <i class="fa-solid fa-chess-knight text-[var(--green)] mr-2"></i>Match Lobby
                        </h2>
                        <p class="text-sm text-[var(--muted)] mb-4">Enter your name and send this link to a friend to start.</p>
                        <div class="flex gap-2 mb-3">
                            <input type="text" id="name-input" maxlength="24" placeholder="Your name"
                                   class="w-full bg-black border border-[var(--line)] text-white p-3 rounded-lg text-sm focus:outline-none">
                        </div>
                        <div class="flex gap-2">
                            <input type="text" id="share-link" readonly class="w-full bg-black border border-[var(--line)] text-[var(--muted)] p-3 rounded-lg text-xs font-mono focus:outline-none">
                            <button id="copy-btn" class="bg-[var(--green)] hover:bg-[#91c95b] text-black font-extrabold px-4 rounded-lg text-sm transition">
                                <i class="fa-solid fa-copy"></i>
                            </button>
                        </div>
                        <button id="join-btn" class="mt-3 w-full bg-white text-black font-extrabold px-4 py-3 rounded-lg text-sm transition hover:bg-gray-200 shadow-lg">
                            Join Match
                        </button>
                    </div>
                </div>

                <div id="game-over-overlay" class="overlay hidden">
                    <div class="bg-[var(--panel)] border border-[var(--line)] p-6 rounded-2xl text-center max-w-[92%] shadow-2xl w-[420px]">
                        <h2 class="text-xl font-bold mb-2 text-white"><i class="fa-solid fa-flag text-red-400 mr-2"></i>Game Over</h2>
                        <p id="game-over-text" class="text-sm text-[var(--muted)] mb-4">The game has ended.</p>
                        <button onclick="window.location.reload()" class="bg-[var(--green)] hover:bg-[#91c95b] text-black font-extrabold px-4 py-3 rounded-lg text-sm transition w-full shadow-lg">Play Again</button>
                    </div>
                </div>

                <div id="spell-banner" class="hidden absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-white px-6 py-4 rounded-2xl font-bold text-center z-50 shadow-[0_0_40px_rgba(0,0,0,0.8)] border border-white/20 w-[90%] max-w-[340px] backdrop-blur-md">
                    <div id="spell-banner-title" class="text-2xl mb-1 drop-shadow-md" style="font-family: 'Cinzel', serif;">SPELL</div>
                    <div id="spell-banner-desc" class="text-sm font-medium text-white/90 mb-4">Action</div>
                    <button onclick="cancelSpell()" class="text-sm bg-black/50 hover:bg-black/70 px-4 py-2 border border-white/10 rounded-lg w-full transition uppercase tracking-wider font-bold">Cancel</button>
                </div>
            </div>

            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 bg-black rounded flex items-center justify-center overflow-hidden border border-[var(--line)] shrink-0 shadow-lg">
                        <img src="https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png" class="w-8 h-8 object-contain drop-shadow" id="my-avatar">
                    </div>
                    <div class="min-w-0">
                        <div class="font-bold text-sm tracking-wide truncate" id="my-name">You</div>
                        <div class="flex items-center mt-0.5 min-h-[18px] flex-wrap gap-1" id="captured-bottom"></div>
                    </div>
                </div>
                <div class="text-xs font-mono font-bold bg-[var(--green)] text-black px-3 py-2 rounded shrink-0 shadow-lg" id="my-status">Thinking</div>
            </div>
        </div>
    </div>

    <!-- Redesigned Grimoire Panel for scrolling -->
    <div class="w-full lg:w-[420px] xl:w-[460px] grimoire-container flex flex-col z-10 lg:h-screen lg:sticky top-0 pb-6 lg:pb-0">
        <div class="p-5 border-b border-[var(--line)] bg-[rgba(0,0,0,0.4)] backdrop-blur-sm sticky top-0 z-20 flex justify-between items-center shadow-md">
            <h3 class="font-bold text-sm text-[#e9d5ff] uppercase tracking-widest flex items-center" style="font-family: 'Cinzel', serif;">
                <i class="fa-solid fa-book-journal-whills mr-2 text-purple-400"></i>The Grimoire
            </h3>
            <span id="turn-indicator" class="text-[10px] font-bold px-2 py-1 rounded bg-black text-[var(--muted)] border border-[var(--line)]">WAITING</span>
        </div>
        
        <div id="spells-container" class="grid grid-cols-2 gap-3 p-4">
            <!-- Spells injected here via JS -->
        </div>

        <div class="px-5 py-3 mt-auto border-t border-[var(--line)] flex justify-between items-center bg-[rgba(0,0,0,0.4)]">
            <span class="font-bold text-xs text-[var(--muted)] uppercase tracking-widest"><i class="fa-solid fa-scroll mr-2"></i>History</span>
            <button id="resign-btn" class="text-xs text-red-400 hover:text-red-300 transition font-bold">
                <i class="fa-solid fa-flag mr-1"></i>Resign
            </button>
        </div>
        <div class="flex-grow max-h-[250px] lg:max-h-[none] overflow-y-auto p-4 font-mono text-sm shadow-inner" id="move-history"></div>
    </div>
</div>

<script>
const socket = io();

let playerId = localStorage.getItem("wizard_chess_id");
if (!playerId) {
    playerId = Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("wizard_chess_id", playerId);
}

const room = (() => {
    const params = new URLSearchParams(location.search);
    let r = params.get("room");
    if (!r) {
        r = Math.random().toString(36).slice(2, 9);
        history.replaceState({}, "", `${location.pathname}?room=${r}`);
    }
    return r;
})();

document.getElementById("share-link").value = location.href;
document.getElementById("copy-btn").onclick = async () => {
    const input = document.getElementById("share-link");
    input.select();
    try { await navigator.clipboard.writeText(input.value); } catch (e) {}
};

const game = new Chess();
let myColor = null;
let myHand = [];
let usedSpells = new Set();
let gameReady = false;
let selectedSquare = null;
let activeSpell = null;
let spellSourceSq = null;
let moveNum = 1;
let playerName = localStorage.getItem("wizard_chess_name") || "";
let pendingJoin = false;

const sounds = {
    move: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3"),
    capture: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3"),
    spell: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3"),
    start: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/game-start.mp3"),
};

function buildBoardDOM() {
    const boardEl = document.getElementById("board");
    boardEl.innerHTML = "";
    const files = ["a","b","c","d","e","f","g","h"];
    const ranks = ["8","7","6","5","4","3","2","1"];

    for (let r = 0; r < 8; r++) {
        for (let f = 0; f < 8; f++) {
            const sq = files[f] + ranks[r];
            const square = document.createElement("div");
            square.className = `square ${(r + f) % 2 === 0 ? "sq-light" : "sq-dark"}`;
            square.id = `sq-${sq}`;
            square.dataset.square = sq;
            square.onclick = () => handleSquareClick(sq);

            const highlight = document.createElement("div");
            highlight.id = `hl-${sq}`;
            highlight.style.display = "none";

            const dot = document.createElement("div");
            dot.id = `dot-${sq}`;
            dot.style.display = "none";

            const piece = document.createElement("div");
            piece.id = `piece-${sq}`;
            piece.className = "piece";
            piece.style.display = "none";

            square.appendChild(highlight);
            square.appendChild(dot);
            square.appendChild(piece);
            boardEl.appendChild(square);
        }
    }
}

function setBoardOrientation() {
    document.getElementById("board-shell").classList.toggle("flipped", myColor === "b");
}

function isMyTurn() {
    return myColor && myColor !== "s" && gameReady && game.turn() === myColor && document.getElementById("game-over-overlay").classList.contains("hidden");
}

function setMoveLogFromSan(text, color, isSpell = false) {
    const history = document.getElementById("move-history");
    const safeText = (text || "").toString();
    const style = isSpell ? "text-purple-300 font-bold drop-shadow-md" : "text-[#e3e3e3]";
    const icon = isSpell ? '<i class="fa-solid fa-bolt text-[10px] mr-1 text-purple-400"></i>' : "";

    if (color === "w") {
        history.insertAdjacentHTML("beforeend", `
            <div class="flex py-1.5 border-b border-[var(--line)]">
                <div class="w-8 text-[var(--muted)]">${moveNum}.</div>
                <div class="w-1/2 ${style}">${icon}${safeText}</div>
                <div class="w-1/2 text-right text-[var(--muted)]" id="black-move-${moveNum}">...</div>
            </div>
        `);
    } else {
        const el = document.getElementById(`black-move-${moveNum}`);
        if (el) {
            el.innerHTML = `<span class="${style}">${icon}${safeText}</span>`;
            el.classList.remove("text-muted");
            el.classList.add("text-left");
        } else {
            history.insertAdjacentHTML("beforeend", `
                <div class="flex py-1.5 border-b border-[var(--line)]">
                    <div class="w-8 text-[var(--muted)]">${moveNum}.</div>
                    <div class="w-1/2"></div>
                    <div class="w-1/2 ${style}">${icon}${safeText}</div>
                </div>
            `);
        }
        moveNum += 1;
    }

    history.scrollTop = history.scrollHeight;
}

function calcMaterial() {
    const counts = { w: {p:0,n:0,b:0,r:0,q:0}, b: {p:0,n:0,b:0,r:0,q:0} };
    const values = { p:1, n:3, b:3, r:5, q:9 };
    const base = { p:8, n:2, b:2, r:2, q:1 };

    for (const file of ["a","b","c","d","e","f","g","h"]) {
        for (const rank of ["1","2","3","4","5","6","7","8"]) {
            const p = game.get(file + rank);
            if (p) counts[p.color][p.type] += 1;
        }
    }

    let wScore = 0, bScore = 0;
    let capW = "", capB = "";

    ["q","r","b","n","p"].forEach(type => {
        const wMissing = base[type] - counts.w[type];
        const bMissing = base[type] - counts.b[type];
        for (let i = 0; i < bMissing; i++) {
            capW += `<div class="mini-piece b${type.toUpperCase()}" style="width:18px;height:18px;display:inline-block;background-size:contain;margin-right:-4px;"></div>`;
            wScore += values[type];
        }
        for (let i = 0; i < wMissing; i++) {
            capB += `<div class="mini-piece w${type.toUpperCase()}" style="width:18px;height:18px;display:inline-block;background-size:contain;margin-right:-4px;"></div>`;
            bScore += values[type];
        }
    });

    const bottomAdv = wScore > bScore ? (myColor === "w" ? wScore - bScore : "") : (bScore > wScore ? (myColor === "b" ? bScore - wScore : "") : "");
    const topAdv = wScore > bScore ? (myColor === "b" ? wScore - bScore : "") : (bScore > wScore ? (myColor === "w" ? bScore - wScore : "") : "");

    document.getElementById("captured-bottom").innerHTML = (myColor === "w" ? capW : capB) + (bottomAdv ? `<span class="text-xs text-[var(--muted)] ml-1 font-bold">+${bottomAdv}</span>` : "");
    document.getElementById("captured-top").innerHTML = (myColor === "w" ? capB : capW) + (topAdv ? `<span class="text-xs text-[var(--muted)] ml-1 font-bold">+${topAdv}</span>` : "");
}

function updateUI() {
    const files = ["a","b","c","d","e","f","g","h"];
    const ranks = ["8","7","6","5","4","3","2","1"];
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
                pieceEl.style.display = "block";
            } else {
                pieceEl.style.display = "none";
                pieceEl.className = "piece";
            }

            hlEl.className = "sq-highlight";
            hlEl.style.display = "none";
            dotEl.style.display = "none";

            if (sq === selectedSquare || sq === spellSourceSq) {
                hlEl.className = "sq-selected";
                hlEl.style.display = "block";
            }

            if (selectedSquare) {
                const isTarget = legalMoves.some(m => m.to === sq);
                if (isTarget) {
                    dotEl.className = p ? "capture-dot" : "move-dot";
                    dotEl.style.display = "block";
                }
            }
        }
    }

    const isMy = game.turn() === myColor;
    const myStatus = document.getElementById("my-status");
    const oppStatus = document.getElementById("opp-status");
    const turnIndicator = document.getElementById("turn-indicator");

    if (gameReady) {
        turnIndicator.innerText = isMy ? "YOUR TURN" : "OPPONENT'S TURN";
        turnIndicator.className = `text-[10px] font-bold px-2 py-1 rounded shadow ${isMy ? "bg-purple-600 text-white border-purple-400" : "bg-black text-[var(--muted)] border-[var(--line)]"}`;
        
        myStatus.innerText = isMy ? "Thinking" : "Waiting";
        myStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow-lg ${isMy ? "bg-[var(--green)] text-black" : "bg-black text-[var(--muted)] border border-[var(--line)]"}`;
        
        oppStatus.innerText = !isMy ? "Thinking" : "Waiting";
        oppStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow border ${!isMy ? "bg-[var(--green)] text-black border-transparent" : "bg-black text-[var(--muted)] border-[var(--line)]"}`;
    }

    const handContainer = document.getElementById("spells-container");
    handContainer.innerHTML = "";

    if (myHand && myColor && myColor !== "s") {
        myHand.forEach(spell => {
            const isUsed = usedSpells.has(spell.id);
            const isActive = activeSpell && activeSpell.id === spell.id;

            const card = document.createElement("div");
            card.className = `spell-card p-3 lg:p-4 flex flex-col items-center justify-start ${isUsed ? "used" : ""} ${isActive ? "active" : ""} ${!isUsed && gameReady && game.turn() === myColor ? "cursor-pointer" : ""}`;
            card.style.setProperty("--spell-color", spell.color);
            card.style.setProperty("--spell-glow", spell.color + "55");

            card.innerHTML = `
                <div class="w-12 h-12 lg:w-16 lg:h-16 mb-2 lg:mb-3 relative drop-shadow-[0_0_6px_${spell.color}99]">
                    ${spell.image}
                </div>
                <div class="text-[11px] lg:text-[13px] font-black tracking-wider uppercase mb-1 text-white text-center shadow-black drop-shadow-md border-b pb-1 w-full" style="border-color:${spell.color}88; font-family: 'Cinzel', serif;">${spell.name}</div>
                <div class="text-[9px] lg:text-[10px] text-gray-400 leading-snug text-center px-1 mt-1 font-medium">${spell.desc}</div>
            `;

            card.onclick = () => {
                if (isUsed || !gameReady || game.turn() !== myColor) return;
                if (isActive) {
                    cancelSpell();
                    return;
                }

                if (spell.type === "instant") {
                    usedSpells.add(spell.id);
                    socket.emit("spell_effect", {
                        room,
                        player_id: playerId,
                        spell_id: spell.id,
                        fen: game.fen(),
                        log: spell.name.toUpperCase()
                    });
                    cancelSpell();
                    return;
                }

                selectedSquare = null;
                activeSpell = spell;
                spellSourceSq = null;
                const banner = document.getElementById("spell-banner");
                document.getElementById("spell-banner-title").innerText = spell.name;
                document.getElementById("spell-banner-title").style.color = spell.color;
                document.getElementById("spell-banner-desc").innerText = spell.desc;
                banner.style.background = `linear-gradient(135deg, ${spell.color}44, rgba(0,0,0,0.8) 60%)`;
                banner.style.border = `1px solid ${spell.color}88`;
                banner.classList.remove("hidden");
                updateUI();
            };

            handContainer.appendChild(card);
        });
    }

    calcMaterial();
}

function cancelSpell() {
    activeSpell = null;
    spellSourceSq = null;
    selectedSquare = null;
    document.getElementById("spell-banner").classList.add("hidden");
    updateUI();
}

function handleSquareClick(sq) {
    if (!gameReady || myColor === "s" || !myColor || game.turn() !== myColor) return;
    if (!document.getElementById("game-over-overlay").classList.contains("hidden")) return;

    if (activeSpell) {
        processSpellClick(sq);
        return;
    }

    const piece = game.get(sq);

    if (piece && piece.color === myColor) {
        selectedSquare = selectedSquare === sq ? null : sq;
        updateUI();
        return;
    }

    if (selectedSquare) {
        const temp = new Chess(game.fen());
        const move = temp.move({ from: selectedSquare, to: sq, promotion: "q" });
        if (move) {
            const san = move.san;
            
            // Optimistic UI updates
            game.move({ from: selectedSquare, to: sq, promotion: "q" });
            if (san.includes("x")) sounds.capture.play().catch(()=>{});
            else sounds.move.play().catch(()=>{});
            setMoveLogFromSan(san, myColor, false);
            
            socket.emit("standard_move", {
                room,
                player_id: playerId,
                from: move.from,
                to: move.to,
                san: san,
                fen: temp.fen()
            });
        }
        selectedSquare = null;
        updateUI();
    }
}

function processSpellClick(sq) {
    const p = game.get(sq);
    const opp = myColor === "w" ? "b" : "w";
    const baseFen = game.fen();
    const temp = new Chess(baseFen);
    let nextFen = null;
    let logText = activeSpell.name.toUpperCase();

    switch (activeSpell.type) {
        case "enemy":
            if (p && p.color === opp && p.type !== "k") {
                temp.remove(sq);
                if (activeSpell.id === "sectum") {
                    temp.put({ type: "p", color: opp }, sq);
                }
                nextFen = temp.fen();
            }
            break;

        case "any": {
            const fileIdx = sq.charCodeAt(0);
            const rankIdx = parseInt(sq[1], 10);
            for (let f = fileIdx - 1; f <= fileIdx + 1; f++) {
                for (let r = rankIdx - 1; r <= rankIdx + 1; r++) {
                    if (f < 97 || f > 104 || r < 1 || r > 8) continue;
                    const targetSq = String.fromCharCode(f) + r;
                    const targetPiece = temp.get(targetSq);
                    if (targetPiece && targetPiece.type !== "k") {
                        temp.remove(targetSq);
                    }
                }
            }
            nextFen = temp.fen();
            break;
        }

        case "own_pawn":
            if (p && p.color === myColor && p.type === "p") {
                temp.remove(sq);
                temp.put({ type: "n", color: myColor }, sq);
                nextFen = temp.fen();
            }
            break;

        case "drag_own":
        case "drag_enemy":
            if (!spellSourceSq) {
                const reqColor = activeSpell.type === "drag_own" ? myColor : opp;
                if (p && p.color === reqColor) {
                    spellSourceSq = sq;
                    updateUI();
                }
                return;
            } else {
                const source = spellSourceSq;
                const fDist = Math.abs(source.charCodeAt(0) - sq.charCodeAt(0));
                const rDist = Math.abs(parseInt(source[1], 10) - parseInt(sq[1], 10));

                if (activeSpell.id === "accio" && (fDist > 2 || rDist > 2)) return;
                if (activeSpell.id === "leviosa" && ((fDist > 1 || rDist > 1) || p)) return;
                if (activeSpell.id === "alohomora") {
                    const ownHalf = myColor === "w" ? parseInt(sq[1], 10) <= 4 : parseInt(sq[1], 10) >= 5;
                    if (!ownHalf || p) return;
                }

                if (activeSpell.id === "imperio") {
                    temp.load(switchTurnInFen(baseFen));
                    const moved = temp.move({ from: source, to: sq, promotion: "q" });
                    if (moved) {
                        nextFen = temp.fen();
                        logText = `IMPERIO: ${moved.san}`;
                    } else {
                        spellSourceSq = null;
                        updateUI();
                        return;
                    }
                    break;
                }

                const sourcePiece = temp.get(source);
                temp.remove(source);
                if (sourcePiece) temp.put(sourcePiece, sq);
                nextFen = temp.fen();
            }
            break;
    }

    if (nextFen) {
        usedSpells.add(activeSpell.id);
        socket.emit("spell_effect", {
            room,
            player_id: playerId,
            spell_id: activeSpell.id,
            fen: nextFen,
            log: logText
        });
        cancelSpell();
    }
}

function switchTurnInFen(fen) {
    const parts = fen.split(" ");
    if (parts.length > 1) parts[1] = parts[1] === "w" ? "b" : "w";
    if (parts.length > 3) parts[3] = "-";
    return parts.join(" ");
}

document.getElementById("resign-btn").onclick = () => {
    if (!gameReady || !myColor || myColor === "s") return;
    socket.emit("resign", { room, player_id: playerId });
};

function joinGame() {
    const nameInput = document.getElementById("name-input");
    const name = (nameInput.value || "").trim().slice(0, 24);
    if (!name) {
        nameInput.focus();
        return;
    }
    playerName = name;
    localStorage.setItem("wizard_chess_name", playerName);
    pendingJoin = true;
    socket.emit("join_room", { room, player_id: playerId, player_name: playerName });
}

document.getElementById("join-btn").onclick = joinGame;
document.getElementById("name-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") joinGame();
});

socket.on("connect", () => {
    document.getElementById("share-link").value = location.href;
    const saved = localStorage.getItem("wizard_chess_name");
    if (saved) {
        document.getElementById("name-input").value = saved;
    }
    if (!pendingJoin) {
        document.getElementById("waiting-overlay").style.display = "flex";
    }
});

socket.on("role_assigned", (data) => {
    myColor = data.color;
    myHand = data.hand || [];
    usedSpells = new Set(data.used || []);

    if (myColor === "w") {
        document.getElementById("my-name").innerText = "You (White)";
        document.getElementById("my-avatar").src = "https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png";
        document.getElementById("opp-name").innerText = "Opponent (Black)";
        document.getElementById("opp-avatar").src = "https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png";
    } else if (myColor === "b") {
        document.getElementById("my-name").innerText = "You (Black)";
        document.getElementById("my-avatar").src = "https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png";
        document.getElementById("opp-name").innerText = "Opponent (White)";
        document.getElementById("opp-avatar").src = "https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png";
    } else {
        document.getElementById("my-name").innerText = "Spectator";
    }

    if (data.snapshot && data.snapshot.fen) {
        game.load(data.snapshot.fen);
    }

    setBoardOrientation();
    buildBoardDOM();
    updateUI();

    if (data.snapshot && data.snapshot.started) {
        document.getElementById("waiting-overlay").style.display = "none";
    }
});

socket.on("room_state", (state) => {
    const waiting = document.getElementById("waiting-overlay");
    if (state.started && !state.game_over) {
        waiting.style.display = "none";
        if (!gameReady) {
            sounds.start.play().catch(() => {});
        }
        gameReady = true;
    }
    updateUI();
});

socket.on("board_update", (data) => {
    const isMyNormalMove = (data.color === myColor && !data.is_spell);

    if (!isMyNormalMove) {
        if (data.fen) game.load(data.fen);
        
        // Log the text
        if (data.san) setMoveLogFromSan(data.san, data.color, !!data.is_spell);
        
        // Visually update the UI first
        updateUI();

        // Let the CSS layout apply before triggering sound
        requestAnimationFrame(() => {
            setTimeout(() => {
                if (data.is_spell) {
                    sounds.spell.play().catch(() => {});
                } else {
                    if ((data.san || "").includes("x")) sounds.capture.play().catch(() => {});
                    else sounds.move.play().catch(() => {});
                }
            }, 50); // slight pause ensures transition begins
        });
    } else {
        // Validation check for optimistic moves
        if (data.fen && game.fen() !== data.fen) game.load(data.fen);
        updateUI();
    }

    if (data.is_spell && data.color === myColor && data.used_spell_id) {
        usedSpells.add(data.used_spell_id);
    }

    if (data.room_state && data.room_state.started) {
        document.getElementById("waiting-overlay").style.display = "none";
        gameReady = true;
    }
});

socket.on("game_over", (data) => {
    const overlay = document.getElementById("game-over-overlay");
    const text = document.getElementById("game-over-text");
    overlay.classList.remove("hidden");
    const youWon = (data.winner === myColor);
    text.innerText = youWon ? "You won by resignation." : `Game over. ${data.winner_name || "Opponent"} won by resignation.`;
    gameReady = false;
    updateUI();
});

buildBoardDOM();
updateUI();

if (playerName) {
    document.getElementById("name-input").value = playerName;
}
</script>
</body>
</html>
'''

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"> SERVER ONLINE. PORT: {port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
