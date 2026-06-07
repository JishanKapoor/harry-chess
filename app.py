import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "wizard_chess_secret_v3")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

SPELLS = [
    {"id": "avada", "name": "Avada Kedavra", "rarity": "Legendary", "icon": "fa-bolt", "type": "enemy", "desc": "Click an enemy piece to destroy it.", "color": "#f59e0b"},
    {"id": "time", "name": "Time-Turner", "rarity": "Legendary", "icon": "fa-hourglass-half", "type": "instant", "desc": "Rewind the board one move.", "color": "#8b5cf6"},
    {"id": "imperio", "name": "Imperio", "rarity": "Rare", "icon": "fa-eye", "type": "drag_enemy", "desc": "Move an enemy piece as your own.", "color": "#14b8a6"},
    {"id": "sectum", "name": "Sectumsempra", "rarity": "Rare", "icon": "fa-droplet", "type": "enemy", "desc": "Demote an enemy piece to a Pawn.", "color": "#ef4444"},
    {"id": "fiendfyre", "name": "Fiendfyre", "rarity": "Rare", "icon": "fa-fire", "type": "any", "desc": "Destroy a 3x3 square area.", "color": "#f97316"},
    {"id": "accio", "name": "Accio", "rarity": "Common", "icon": "fa-magnet", "type": "drag_own", "desc": "Move your piece up to 2 squares.", "color": "#22c55e"},
    {"id": "leviosa", "name": "Wingardium Leviosa", "rarity": "Common", "icon": "fa-feather", "type": "drag_own", "desc": "Move to an adjacent empty square.", "color": "#06b6d4"},
    {"id": "alohomora", "name": "Alohomora", "rarity": "Common", "icon": "fa-key", "type": "drag_own", "desc": "Move to any empty square on your half.", "color": "#84cc16"},
    {"id": "expelliarmus", "name": "Expelliarmus", "rarity": "Common", "icon": "fa-wand-magic-sparkles", "type": "instant", "desc": "Disarm: Opponent loses a random spell.", "color": "#ec4899"},
    {"id": "protego", "name": "Protego", "rarity": "Common", "icon": "fa-shield-halved", "type": "own_pawn", "desc": "Promote your Pawn to a Knight.", "color": "#3b82f6"},
]

ROOMS = {}

def fen_side_to_move(fen: str) -> str:
    try:
        return fen.split()[1]
    except Exception:
        return "w"

def fresh_hand():
    legendary = [s for s in SPELLS if s["rarity"] == "Legendary"]
    rare = [s for s in SPELLS if s["rarity"] == "Rare"]
    common = [s for s in SPELLS if s["rarity"] == "Common"]

    hand = []
    if legendary:
        hand.append(random.choice(legendary))

    rare_count = min(len(rare), random.randint(1, 2))
    common_count = min(len(common), random.randint(2, 4))

    if rare_count:
        hand.extend(random.sample(rare, rare_count))
    if common_count:
        hand.extend(random.sample(common, common_count))

    random.shuffle(hand)
    return hand

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

    if spell_id == "time":
        if len(room["history"]) < 2:
            return
        room["history"].pop()
        fen = room["history"][-1]
        room["turn"] = fen_side_to_move(fen)
    else:
        if not fen:
            return

        if spell_id == "expelliarmus":
            opp = "b" if color == "w" else "w"
            if room["hands"].get(opp):
                available = [s for s in room["hands"][opp] if s["id"] not in room["used"][opp]]
                if available:
                    removed = random.choice(available)
                    room["used"][opp].add(removed["id"])
                    log_text = f"EXPELLIARMUS (Disarmed {removed['name']})"
                else:
                    log_text = "EXPELLIARMUS (Nothing to disarm)"

        # FORCE TURN SWAP for all standard spells so player cannot keep moving
        next_turn = "b" if color == "w" else "w"
        room["turn"] = next_turn

        parts = fen.split(" ")
        if len(parts) > 1:
            parts[1] = next_turn
        if len(parts) > 3:
            parts[3] = "-"  # Clear en passant target
        if color == "b" and len(parts) > 5:
            try:
                parts[5] = str(int(parts[5]) + 1)
            except:
                pass
        fen = " ".join(parts)

    room["used"][color].add(spell_id)
    room["fen"] = fen
    room["last_action"] = {
        "type": "spell",
        "color": color,
        "spell_id": spell_id,
        "log": log_text,
    }
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

    # Sync spells just in case Expelliarmus removed a card
    emit("sync_spells", {
        "used": {
            "w": list(room["used"]["w"]),
            "b": list(room["used"]["b"])
        }
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <title>Wizard's Chess</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        :root {
            --bg: #1a1622;
            --panel: #262032;
            --panel-2: #1e1928;
            --line: #3f354e;
            --muted: #a79cb7;
            --light: #ebecd0;
            --dark: #739552;
        }

        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: #fff;
            overscroll-behavior: none;
            overflow: hidden;
        }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--panel); }
        ::-webkit-scrollbar-thumb { background: #4a3b5c; border-radius: 999px; }

        .text-muted { color: var(--muted); }

        .sq-light { background: var(--light); }
        .sq-dark { background: var(--dark); }

        .board-shell {
            width: 100%;
            aspect-ratio: 1 / 1;
            position: relative;
            border-radius: 16px;
            overflow: hidden;
            border: 4px solid var(--panel);
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.45);
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

        /* Improved Grimoire styling */
        .grimoire-container {
            background: linear-gradient(180deg, #231c2c, #16121c);
            border-left: 1px solid #3c314a;
            box-shadow: -5px 0 25px rgba(0,0,0,0.4);
        }
        
        .grimoire-header {
            background: rgba(0, 0, 0, 0.2);
            border-bottom: 1px solid #3c314a;
        }

        .spell-card {
            background: linear-gradient(145deg, #2b2238, #1c1524);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 12px;
            position: relative;
            overflow: hidden;
            transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
            padding: 0.75rem;
        }
        
        .spell-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--spell-color);
            opacity: 0.8;
        }

        .spell-card:hover:not(.used) {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 0 10px 20px rgba(0,0,0,0.4), 0 0 15px var(--spell-glow);
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
            filter: grayscale(0.9);
            cursor: not-allowed;
        }

        .overlay {
            position: absolute;
            inset: 0;
            background: rgba(0,0,0,0.68);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 50;
        }

        .game-root {
            height: 100vh;
        }

        .shell-left {
            min-width: 0;
        }

        .board-holder {
            width: 100%;
            max-width: min(85vh, 100%);
            margin: 0 auto;
        }

        #move-history {
            background: #110e16;
            color: #d1c5e0;
        }
    </style>
</head>
<body>
<div class="game-root flex flex-col lg:flex-row">
    <div class="flex-1 flex flex-col justify-center p-2 lg:p-4 overflow-hidden shell-left">
        <div class="board-holder space-y-2 lg:space-y-3">
            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 bg-[#1f1e1b] rounded flex items-center justify-center overflow-hidden border border-[#3f3e3b] shrink-0">
                        <img src="https://images.chesscomfiles.com/chess-themes/pieces/neo/150/bp.png" class="w-8 h-8 object-contain" id="opp-avatar">
                    </div>
                    <div class="min-w-0">
                        <div class="font-bold text-sm tracking-wide truncate" id="opp-name">Opponent</div>
                        <div class="flex items-center mt-0.5 min-h-[18px] flex-wrap gap-1" id="captured-top"></div>
                    </div>
                </div>
                <div class="text-xs font-mono font-bold bg-[#1f1e1b] text-muted px-3 py-2 rounded shrink-0" id="opp-status">Waiting</div>
            </div>

            <div class="board-shell" id="board-shell">
                <div id="board" class="w-full h-full grid grid-cols-8 grid-rows-8 select-none"></div>

                <div id="waiting-overlay" class="overlay">
                    <div class="bg-[#262421] border border-[#3f3e3b] p-6 rounded-2xl text-center max-w-[92%] shadow-2xl w-[420px]">
                        <h2 class="text-xl font-bold mb-2 text-white">
                            <i class="fa-solid fa-chess-knight text-[#81b64c] mr-2"></i>Match Lobby
                        </h2>
                        <p class="text-sm text-muted mb-4">Enter your name and send this link to a friend to start the match.</p>
                        <div class="flex gap-2 mb-3">
                            <input type="text" id="name-input" maxlength="24" placeholder="Your name"
                                   class="w-full bg-[#141312] border border-[#3f3e3b] text-white p-3 rounded-lg text-sm focus:outline-none">
                        </div>
                        <div class="flex gap-2">
                            <input type="text" id="share-link" readonly class="w-full bg-[#141312] border border-[#3f3e3b] text-white p-3 rounded-lg text-xs font-mono focus:outline-none">
                            <button id="copy-btn" class="bg-[#81b64c] hover:bg-[#a3d160] text-black font-extrabold px-4 rounded-lg text-sm transition">
                                <i class="fa-solid fa-copy"></i>
                            </button>
                        </div>
                        <button id="join-btn" class="mt-3 w-full bg-white text-black font-extrabold px-4 py-3 rounded-lg text-sm transition hover:opacity-90">
                            Join Match
                        </button>
                    </div>
                </div>

                <div id="game-over-overlay" class="overlay hidden">
                    <div class="bg-[#262421] border border-[#3f3e3b] p-6 rounded-2xl text-center max-w-[92%] shadow-2xl w-[420px]">
                        <h2 class="text-xl font-bold mb-2 text-white"><i class="fa-solid fa-flag text-red-400 mr-2"></i>Game Over</h2>
                        <p id="game-over-text" class="text-sm text-muted mb-4">The game has ended.</p>
                        <button onclick="window.location.reload()" class="bg-[#81b64c] hover:bg-[#a3d160] text-black font-extrabold px-4 py-3 rounded-lg text-sm transition w-full">Play Again</button>
                    </div>
                </div>

                <div id="spell-banner" class="hidden absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-white px-6 py-4 rounded-2xl font-bold text-center z-50 shadow-[0_0_30px_rgba(168,85,247,0.45)] border border-white/20 w-[90%] max-w-[340px]">
                    <div id="spell-banner-title" class="text-xl mb-1 drop-shadow-md">SPELL</div>
                    <div id="spell-banner-desc" class="text-sm font-medium text-white/90 mb-4">Action</div>
                    <button onclick="cancelSpell()" class="text-sm bg-black/35 hover:bg-black/55 px-4 py-2 rounded-lg w-full transition uppercase tracking-wider font-bold">Cancel</button>
                </div>
            </div>

            <div class="flex justify-between items-center px-2">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 bg-[#1f1e1b] rounded flex items-center justify-center overflow-hidden border border-[#3f3e3b] shrink-0">
                        <img src="https://images.chesscomfiles.com/chess-themes/pieces/neo/150/wp.png" class="w-8 h-8 object-contain" id="my-avatar">
                    </div>
                    <div class="min-w-0">
                        <div class="font-bold text-sm tracking-wide truncate" id="my-name">You</div>
                        <div class="flex items-center mt-0.5 min-h-[18px] flex-wrap gap-1" id="captured-bottom"></div>
                    </div>
                </div>
                <div class="text-xs font-mono font-bold bg-[#81b64c] text-black px-3 py-2 rounded shrink-0" id="my-status">Thinking</div>
            </div>
        </div>
    </div>

    <!-- Redesigned Grimoire Panel -->
    <div class="w-full lg:w-[380px] xl:w-[420px] grimoire-container flex flex-col h-[35vh] lg:h-full z-10 flex-shrink-0">
        <div class="p-4 grimoire-header flex justify-between items-center">
            <h3 class="font-bold text-sm text-[#d1c5e0] uppercase tracking-widest flex items-center">
                <i class="fa-solid fa-book-journal-whills mr-2 text-[#8b5cf6]"></i>Your Grimoire
            </h3>
            <span id="turn-indicator" class="text-[10px] font-bold px-2 py-1 rounded bg-[#1f1e1b] text-muted">WAITING</span>
        </div>
        
        <div id="spells-container" class="flex lg:grid lg:grid-cols-2 gap-3 overflow-x-auto lg:overflow-y-auto p-4 max-h-[300px]">
        </div>

        <div class="px-4 py-3 border-y border-[#3c314a] flex justify-between items-center bg-[rgba(0,0,0,0.2)]">
            <span class="font-bold text-xs text-[#a79cb7] uppercase tracking-widest"><i class="fa-solid fa-list-ul mr-2"></i>Match Log</span>
            <button id="resign-btn" class="text-xs text-red-400 hover:text-red-300 transition font-bold">
                <i class="fa-solid fa-flag mr-1"></i>Resign
            </button>
        </div>
        <div class="flex-grow overflow-y-auto p-4 font-mono text-sm shadow-inner" id="move-history"></div>
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
    const style = isSpell ? "text-[#b490e5] font-bold" : "text-[#d1c5e0]";
    const icon = isSpell ? '<i class="fa-solid fa-wand-magic-sparkles text-[10px] mr-1"></i>' : "";

    if (color === "w") {
        history.insertAdjacentHTML("beforeend", `
            <div class="flex py-1.5 border-b border-[#3c314a]">
                <div class="w-8 text-[#a79cb7]">${moveNum}.</div>
                <div class="w-1/2 ${style}">${icon}${safeText}</div>
                <div class="w-1/2 text-right text-[#a79cb7]" id="black-move-${moveNum}">...</div>
            </div>
        `);
    } else {
        const el = document.getElementById(`black-move-${moveNum}`);
        if (el) {
            el.innerHTML = `<span class="${style}">${icon}${safeText}</span>`;
            el.classList.remove("text-muted", "text-[#a79cb7]");
            el.classList.add("text-left");
        } else {
            history.insertAdjacentHTML("beforeend", `
                <div class="flex py-1.5 border-b border-[#3c314a]">
                    <div class="w-8 text-[#a79cb7]">${moveNum}.</div>
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

    document.getElementById("captured-bottom").innerHTML = (myColor === "w" ? capW : capB) + (bottomAdv ? `<span class="text-xs text-muted ml-1 font-bold">+${bottomAdv}</span>` : "");
    document.getElementById("captured-top").innerHTML = (myColor === "w" ? capB : capW) + (topAdv ? `<span class="text-xs text-muted ml-1 font-bold">+${topAdv}</span>` : "");
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
        turnIndicator.className = `text-[10px] font-bold px-2 py-1 rounded shadow ${isMy ? "bg-[#8b5cf6] text-white" : "bg-[#1f1e1b] text-muted"}`;
        myStatus.innerText = isMy ? "Thinking" : "Waiting";
        myStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow ${isMy ? "bg-[#8b5cf6] text-white" : "bg-[#1f1e1b] text-muted"}`;
        oppStatus.innerText = !isMy ? "Thinking" : "Waiting";
        oppStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow ${!isMy ? "bg-[#8b5cf6] text-white" : "bg-[#1f1e1b] text-muted"}`;
    }

    const handContainer = document.getElementById("spells-container");
    handContainer.innerHTML = "";

    if (myHand && myColor && myColor !== "s") {
        myHand.forEach(spell => {
            const isUsed = usedSpells.has(spell.id);
            const isActive = activeSpell && activeSpell.id === spell.id;

            const card = document.createElement("div");
            card.className = `spell-card min-w-[140px] lg:w-auto text-center flex flex-col items-center justify-center ${isUsed ? "used" : ""} ${isActive ? "active" : ""} ${!isUsed && gameReady && game.turn() === myColor ? "cursor-pointer" : ""}`;
            card.style.setProperty("--spell-color", spell.color);
            card.style.setProperty("--spell-glow", spell.color + "66");

            card.innerHTML = `
                <div class="text-2xl mb-1.5 drop-shadow-md" style="color:${spell.color}"><i class="fa-solid ${spell.icon}"></i></div>
                <div class="text-[11px] font-bold leading-tight mb-1 text-white tracking-wide uppercase">${spell.name}</div>
                <div class="text-[10px] text-[#a79cb7] leading-snug hidden lg:block">${spell.desc}</div>
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
                document.getElementById("spell-banner-title").innerHTML = `<i class="fa-solid ${spell.icon} mr-2"></i>${spell.name}`;
                document.getElementById("spell-banner-title").style.color = spell.color;
                document.getElementById("spell-banner-desc").innerText = spell.desc;
                banner.style.background = `linear-gradient(135deg, ${spell.color}bb, #2d2436 75%)`;
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
            const nextFen = temp.fen();
            
            // --- OPTIMISTIC UI UPDATE --- 
            // Apply the move immediately to prevent any UI flickering or lag
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
                fen: nextFen
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

socket.on("sync_spells", (data) => {
    if (myColor && data.used[myColor]) {
        usedSpells = new Set(data.used[myColor]);
        updateUI();
    }
});

socket.on("board_update", (data) => {
    const isMyNormalMove = (data.color === myColor && !data.is_spell);

    // If it's NOT our normal move, parse the update fully
    if (!isMyNormalMove) {
        if (data.fen) game.load(data.fen);
        
        if (data.is_spell) {
            sounds.spell.play().catch(() => {});
        } else {
            if ((data.san || "").includes("x")) sounds.capture.play().catch(() => {});
            else sounds.move.play().catch(() => {});
        }
        
        if (data.san) {
            setMoveLogFromSan(data.san, data.color, !!data.is_spell);
        }
    } else {
        // If it was our standard move, we already simulated the visuals/sounds optimistically
        // Just enforce the FEN string check in case of desync
        if (data.fen && game.fen() !== data.fen) {
            game.load(data.fen);
        }
    }

    if (data.is_spell && data.color === myColor && data.used_spell_id) {
        usedSpells.add(data.used_spell_id);
    }

    if (data.room_state && data.room_state.started) {
        document.getElementById("waiting-overlay").style.display = "none";
        gameReady = true;
    }

    updateUI();
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
