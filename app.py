import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "wizard_chess_secret_v5")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

SVG_TIME = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="45" fill="none" stroke="#eab308" stroke-width="3" stroke-dasharray="10 5"/><circle cx="50" cy="50" r="38" fill="none" stroke="#eab308" stroke-width="2"/><path d="M40 30 L60 30 L50 50 Z" fill="#fef08a"/><path d="M40 70 L60 70 L50 50 Z" fill="#ca8a04"/><path d="M35 25 L65 25 M35 75 L65 75" stroke="#eab308" stroke-width="4" stroke-linecap="round"/><circle cx="50" cy="50" r="8" fill="#fef08a"/></svg>'''

SVG_AVADA = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="none" stroke="#22c55e" stroke-width="4" stroke-dasharray="4 8" filter="drop-shadow(0 0 10px #22c55e)"/><path d="M60 15 L35 50 L55 55 L40 85 L75 45 L50 40 Z" fill="#4ade80" filter="drop-shadow(0 0 15px #22c55e)"/></svg>'''

SVG_IMPERIO = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M10 50 Q50 10 90 50 Q50 90 10 50 Z" fill="none" stroke="#ec4899" stroke-width="4"/><circle cx="50" cy="50" r="18" fill="#f472b6" filter="drop-shadow(0 0 12px #ec4899)"/><circle cx="50" cy="50" r="6" fill="#831843"/><path d="M50 68 L35 100 M50 68 L50 100 M50 68 L65 100" stroke="#fbcfe8" stroke-width="2" stroke-dasharray="4 4"/></svg>'''

SVG_SECTUM = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M20 20 L80 80 M30 10 L90 70 M10 30 L70 90" stroke="#d1d5db" stroke-width="4" stroke-linecap="round"/><path d="M50 50 Q60 70 50 80 Q40 70 50 50 Z" fill="#ef4444" filter="drop-shadow(0 0 5px #ef4444)"/><circle cx="70" cy="40" r="4" fill="#ef4444"/><circle cx="30" cy="70" r="3" fill="#ef4444"/></svg>'''

SVG_FIENDFYRE = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M50 95 C20 95 25 60 40 40 C35 30 25 25 30 15 C45 25 45 40 50 30 C55 40 55 25 70 15 C75 25 65 30 60 40 C75 60 80 95 50 95 Z" fill="#ea580c" filter="drop-shadow(0 0 8px #f97316)"/><path d="M50 85 C35 85 38 65 45 50 C48 40 52 40 55 50 C62 65 65 85 50 85 Z" fill="#fb923c"/><circle cx="42" cy="65" r="3" fill="#7c2d12"/><circle cx="58" cy="65" r="3" fill="#7c2d12"/></svg>'''

SVG_PORTKEY = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="portalGlow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#ffffff"/><stop offset="40%" stop-color="#3b82f6"/><stop offset="80%" stop-color="#1e3a8a"/><stop offset="100%" stop-color="#000000" stop-opacity="0"/></radialGradient></defs><circle cx="50" cy="50" r="45" fill="url(#portalGlow)" filter="drop-shadow(0 0 10px #60a5fa)"/><path d="M50 15 Q75 25 85 50 Q75 75 50 85 Q25 75 15 50 Q25 25 50 15 Z" fill="none" stroke="#93c5fd" stroke-width="3" stroke-dasharray="6 4"/><circle cx="50" cy="50" r="12" fill="#ffffff" filter="drop-shadow(0 0 8px #fff)"/><path d="M50 10 L50 0 M50 90 L50 100 M10 50 L0 50 M90 50 L100 50" stroke="#bfdbfe" stroke-width="4" stroke-linecap="round"/></svg>'''

SVG_EXPELLIARMUS = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M20 80 L80 20" stroke="#78350f" stroke-width="8" stroke-linecap="round"/><path d="M70 30 L80 20" stroke="#fbbf24" stroke-width="8" stroke-linecap="round"/><circle cx="80" cy="20" r="12" fill="none" stroke="#ef4444" stroke-width="3" filter="drop-shadow(0 0 8px #ef4444)"/><path d="M80 5 L80 15 M80 25 L80 35 M65 20 L75 20 M85 20 L95 20 M70 10 L75 15 M85 25 L90 30 M70 30 L75 25 M85 10 L90 15" stroke="#ef4444" stroke-width="3" stroke-linecap="round"/></svg>'''

SVG_PROTEGO = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M50 10 L90 30 L90 60 Q90 90 50 95 Q10 90 10 60 L10 30 Z" fill="none" stroke="#3b82f6" stroke-width="6" filter="drop-shadow(0 0 10px #60a5fa)"/><path d="M50 20 L80 35 L80 55 Q80 80 50 85 Q20 80 20 55 L20 35 Z" fill="#1e3a8a" opacity="0.6"/><path d="M30 30 L70 70 M30 70 L70 30" stroke="#60a5fa" stroke-width="2" opacity="0.5"/></svg>'''

SVG_ALOHOMORA = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="30" cy="50" r="15" fill="none" stroke="#eab308" stroke-width="6" filter="drop-shadow(0 0 6px #facc15)"/><path d="M45 50 L85 50 M75 50 L75 65 M65 50 L65 65" stroke="#eab308" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="30" cy="50" r="5" fill="#ca8a04"/></svg>'''

SVG_LEVIOSA = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M20 80 Q10 50 40 40 Q50 20 80 20 Q70 50 60 60 Q40 90 20 80 Z" fill="#f3f4f6" stroke="#9ca3af" stroke-width="2" filter="drop-shadow(0 0 10px #ffffff)"/><path d="M20 80 Q40 70 80 20" stroke="#d1d5db" stroke-width="2" fill="none"/><path d="M20 90 Q50 100 80 90" stroke="#e5e7eb" stroke-width="3" stroke-dasharray="5 5" fill="none"/></svg>'''

SVG_BOMBARDA = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><path d="M50 10 L60 35 L85 30 L70 50 L90 70 L65 65 L50 90 L35 65 L10 70 L30 50 L15 30 L40 35 Z" fill="#ef4444" filter="drop-shadow(0 0 12px #dc2626)"/><path d="M50 25 L55 40 L70 40 L60 50 L65 65 L50 55 L35 65 L40 50 L30 40 L45 40 Z" fill="#facc15"/><circle cx="50" cy="50" r="8" fill="#ffffff" filter="drop-shadow(0 0 5px #fff)"/></svg>'''

SVG_PETRIFICUS = '''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><rect x="25" y="35" width="50" height="45" rx="8" fill="#0891b2" stroke="#67e8f9" stroke-width="4" filter="drop-shadow(0 0 10px #06b6d4)"/><path d="M35 35 V20 A15 15 0 0 1 65 20 V35" fill="none" stroke="#67e8f9" stroke-width="8" stroke-linecap="round"/><circle cx="50" cy="57" r="7" fill="#cffafe"/><path d="M47 64 L44 76 H56 L53 64" fill="#cffafe"/><path d="M15 50 L5 50 M85 50 L95 50 M50 15 L50 5 M50 85 L50 95 M25 25 L15 15 M75 25 L85 15 M25 75 L15 85 M75 75 L85 85" stroke="#a5f3fc" stroke-width="4" stroke-linecap="round"/></svg>'''

TIME_TURNER = {"id": "time", "name": "Time-Turner", "type": "instant", "desc": "Rewind the board to before opponent's last move. (Pop 1 from history + your turn again)", "color": "#eab308", "image": SVG_TIME}

SPELLS_POOL = [
    {"id": "avada", "name": "Avada Kedavra", "type": "enemy", "desc": "Click an enemy piece to destroy it.", "color": "#22c55e", "image": SVG_AVADA},
    {"id": "imperio", "name": "Imperio", "type": "drag_enemy", "desc": "Move an enemy piece as your own (not King).", "color": "#ec4899", "image": SVG_IMPERIO},
    {"id": "sectum", "name": "Sectumsempra", "type": "enemy", "desc": "Demote an enemy piece to a Pawn (not King, not rank 1/8).", "color": "#ef4444", "image": SVG_SECTUM},
    {"id": "fiendfyre", "name": "Fiendfyre", "type": "any", "desc": "Destroy a 3x3 square area completely (Kings immune).", "color": "#f97316", "image": SVG_FIENDFYRE},
    {"id": "portkey", "name": "Portkey", "type": "drag_own", "desc": "Teleport your piece to ANY empty square.", "color": "#3b82f6", "image": SVG_PORTKEY},
    {"id": "expelliarmus", "name": "Expelliarmus", "type": "instant", "desc": "Disarm: Destroy a random spell from opponent.", "color": "#ef4444", "image": SVG_EXPELLIARMUS},
    {"id": "protego", "name": "Protego", "type": "own_pawn", "desc": "Promote your Pawn to a Knight instantly.", "color": "#60a5fa", "image": SVG_PROTEGO},
    {"id": "alohomora", "name": "Alohomora", "type": "drag_own", "desc": "Teleport your piece to any empty square on your half.", "color": "#eab308", "image": SVG_ALOHOMORA},
    {"id": "leviosa", "name": "Leviosa", "type": "drag_own", "desc": "Float your piece to an adjacent empty square.", "color": "#f3f4f6", "image": SVG_LEVIOSA},
    {"id": "bombarda", "name": "Bombarda", "type": "bombarda", "desc": "Explode a cross-shaped area (+). Kings immune.", "color": "#dc2626", "image": SVG_BOMBARDA},
    {"id": "petrificus", "name": "Petrificus Totalus", "type": "instant", "desc": "Paralyze opponent: Make 2 consecutive moves!", "color": "#06b6d4", "image": SVG_PETRIFICUS},
]

ROOMS = {}

def fen_side_to_move(fen: str) -> str:
    try:
        return fen.split()[1]
    except Exception:
        return "w"

def get_room(room_id: str):
    if room_id not in ROOMS:
        shuffled_pool = random.sample(SPELLS_POOL, len(SPELLS_POOL))
        hand_w = shuffled_pool[0:5] + [TIME_TURNER]
        hand_b = shuffled_pool[5:10] + [TIME_TURNER]
        random.shuffle(hand_w)
        random.shuffle(hand_b)
        ROOMS[room_id] = {
            "fen": START_FEN,
            "turn": "w",
            "extra_turn": None,
            "history": [START_FEN],
            "player_ids": {"w": None, "b": None},
            "player_names": {"w": "White", "b": "Black"},
            "hands": {"w": hand_w, "b": hand_b},
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

    opp_color = "b" if color == "w" else ("w" if color == "b" else None)
    opp_hand = room["hands"].get(opp_color, []) if opp_color else []
    opp_used_list = list(room["used"].get(opp_color, set())) if opp_color else []

    emit("role_assigned", {
        "color": color,
        "hand": room["hands"].get(color, []) if color in ("w", "b") else [],
        "used": list(room["used"].get(color, set())) if color in ("w", "b") else [],
        "opp_hand": opp_hand,
        "opp_used": opp_used_list,
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

    if room.get("extra_turn") == color:
        # Consume the extra turn (from Petrificus). After this action, switch normally.
        room["extra_turn"] = None
        room["fen"] = fen
        room["turn"] = fen_side_to_move(fen)
    else:
        room["fen"] = fen
        room["turn"] = fen_side_to_move(fen)

    room["history"].append(room["fen"])
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
        # FIX: Pop ONLY once to rewind to BEFORE opponent's last move (not your own too).
        # Then force turn back to caster so they get to choose a different move from that position.
        room["history"].pop()
        fen = room["history"][-1]
        room["turn"] = color
        room["extra_turn"] = None
        # Update fen string turn + clear ep
        parts = fen.split(" ")
        if len(parts) > 1:
            parts[1] = color
        if len(parts) > 3:
            parts[3] = "-"
        fen = " ".join(parts)
        log_text = "TIME-TURNER (Reversed opponent's last move)"
    else:
        if not fen:
            return

        if spell_id == "expelliarmus":
            opp = "b" if color == "w" else "w"
            available = [s for s in room["hands"].get(opp, []) if s["id"] not in room["used"][opp]]
            if available:
                removed = random.choice(available)
                room["used"][opp].add(removed["id"])
                log_text = f"EXPELLIARMUS (Disarmed {removed['name']})"
            else:
                log_text = "EXPELLIARMUS (Nothing to disarm)"

        if spell_id == "petrificus":
            room["extra_turn"] = color
            next_turn = color
            log_text = "PETRIFICUS TOTALUS (Double Move!)"
        else:
            # FIX for extra_turn consistency (prevents infinite/paused turns after Petrificus + spell)
            if room.get("extra_turn") == color:
                next_turn = "b" if color == "w" else "w"
                room["extra_turn"] = None
            else:
                next_turn = "b" if color == "w" else "w"

        room["turn"] = next_turn
        parts = fen.split(" ")
        if len(parts) > 1:
            parts[1] = next_turn
        if len(parts) > 3:
            parts[3] = "-"
        if next_turn == "w" and color == "b" and len(parts) > 5:
            try:
                parts[5] = str(int(parts[5]) + 1)
            except Exception:
                pass
        fen = " ".join(parts)

    board_part = fen.split(" ")[0]
    w_king_alive = "K" in board_part
    b_king_alive = "k" in board_part

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

    emit("sync_spells", {"used": {"w": list(room["used"]["w"]), "b": list(room["used"]["b"])}}, to=room_id)

    if not w_king_alive or not b_king_alive:
        room["game_over"] = True
        if not w_king_alive and not b_king_alive:
            room["winner"] = "draw"
            reason = "Mutual Destruction! Both Kings have fallen beyond the veil."
        elif not w_king_alive:
            room["winner"] = "b"
            reason = "The White King has been obliterated by a dark curse! Black wins!"
        else:
            room["winner"] = "w"
            reason = "The Black King has been obliterated by a dark curse! White wins!"

        emit("game_over", {
            "winner": room["winner"],
            "winner_name": room["player_names"].get(room["winner"], "Opponent") if room["winner"] != "draw" else "Nobody",
            "reason": reason,
            "room_state": room_snapshot(room_id),
        }, to=room_id)

@socketio.on("claim_win")
def handle_claim_win(data):
    room_id = data.get("room")
    winner = data.get("winner")
    reason = data.get("reason")

    room = ROOMS.get(room_id)
    if not room or room["game_over"]:
        return

    room["game_over"] = True
    room["winner"] = winner

    emit("game_over", {
        "winner": winner,
        "winner_name": room["player_names"].get(winner, "Opponent") if winner != "draw" else "Nobody",
        "reason": reason,
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

    loser_name = room["player_names"].get(color, "Opponent")

    emit("game_over", {
        "winner": room["winner"],
        "winner_name": room["player_names"].get(room["winner"], "Opponent"),
        "resigned_color": color,
        "reason": f"{loser_name} has fled via Floo Powder!",
        "room_state": room_snapshot(room_id),
    }, to=room_id)

HTML_PAYLOAD = r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Wizard's Chess</title>
    <link rel="preload" as="image" href="https://images6.alphacoders.com/130/thumb-1920-1305167.jpg">
    <style>
        html, body { margin: 0; background: #000; }
    </style>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Cinzel:wght@600;800&display=swap');

        :root {
            --bg: #302e2b;
            --panel: #262421;
            --panel-2: #1f1e1b;
            --line: #3f3e3b;
            --muted: #a7a6a2;
            --green: #81b64c;
            --light: #ebecd0;
            --dark: #739552;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            font-family: 'Inter', sans-serif;
            color: #fff;
            min-height: 100vh;
            background:
                linear-gradient(rgba(0,0,0,0.58), rgba(0,0,0,0.72)),
                url("https://images6.alphacoders.com/130/thumb-1920-1305167.jpg");
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: #4a3b5c; border-radius: 999px; }

        .sq-light { background: var(--light); }
        .sq-dark { background: var(--dark); }

        .board-shell {
            width: 100%;
            aspect-ratio: 1 / 1;
            position: relative;
            border-radius: 8px;
            overflow: hidden;
            border: 4px solid rgba(255,255,255,0.08);
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
            transition: transform 0.18s ease;
            background: #000;
        }

        .board-shell.flipped #board { transform: rotate(180deg); }
        .board-shell.flipped .piece { transform: rotate(180deg); }

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

        .sq-selected { position:absolute; inset:0; background: rgba(20,85,30,0.5); pointer-events:none; }
        .sq-highlight { position:absolute; inset:0; background: rgba(255,255,51,0.35); pointer-events:none; }
        
        .sq-check { 
            position:absolute; 
            inset:0; 
            background: radial-gradient(ellipse at center, rgba(235, 97, 80, 0.9) 0%, transparent 75%); 
            pointer-events:none; 
            z-index: 5;
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

        .grimoire-container {
            background-color: rgba(31, 30, 27, 0.95);
            border-left: 1px solid var(--line);
            box-shadow: -10px 0 30px rgba(0,0,0,0.6);
        }

        .spell-card {
            background: rgba(38, 36, 33, 0.96);
            border: 2px solid var(--line);
            position: relative;
            overflow: hidden;
            transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
            border-radius: 12px;
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
            opacity: 0.3;
            filter: grayscale(1) brightness(0.6);
            pointer-events: none;
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

        .board-holder {
            width: 100%;
            max-width: min(100%, 85vh);
            margin: 0 auto;
        }

        #move-history {
            background: rgba(0,0,0,0.2);
            color: #d1c5e0;
        }

        .music-btn {
            position: fixed;
            left: 16px;
            bottom: 16px;
            z-index: 9999;
            border: 1px solid rgba(212,175,55,0.55);
            background: linear-gradient(180deg, rgba(212,175,55,0.95), rgba(159,128,20,0.95));
            color: #0b0b0b;
            font-weight: 800;
            padding: 12px 16px;
            border-radius: 14px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.45);
            cursor: pointer;
        }

        .music-btn:hover { filter: brightness(1.05); }
    </style>
</head>
<body>
<audio id="bgMusic" loop preload="auto">
    <source src="https://raw.githubusercontent.com/JishanKapoor/harry-chess/main/YTDown_YouTube_Willow-Weep-For-Me-2018-Stereo-Mix_Media_NJYzpNHJ2mY_009_128k.mp3" type="audio/mpeg">
</audio>
<button id="music-toggle" class="music-btn">♫ Music Off</button>

<div class="game-root flex flex-col lg:flex-row">
    <!-- LEFT: Opponent's Grimoire (View Only) -->
    <div class="hidden lg:flex lg:w-72 xl:w-80 flex-col grimoire-container border-r border-[var(--line)] lg:h-screen lg:overflow-y-auto lg:sticky top-0 pb-6" id="opp-grimoire-panel">
        <div class="p-4 border-b border-[var(--line)] bg-[var(--panel)] sticky top-0 z-20">
            <h3 class="font-bold text-sm text-white uppercase tracking-widest flex items-center" style="font-family: 'Cinzel', serif;">
                <i class="fa-solid fa-user-secret mr-2 text-[var(--green)]"></i>Opponent's Grimoire
            </h3>
            <div class="text-[10px] text-[var(--muted)] mt-1">View only • You cannot cast these</div>
        </div>
        <div id="opp-spells-container" class="grid grid-cols-1 gap-2 p-3"></div>
    </div>

    <!-- CENTER: Board Area -->
    <div class="flex-1 flex flex-col justify-center p-2 lg:p-4 min-w-0">
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
                        <div id="lobby-content">
                            <h2 class="text-xl font-bold mb-2 text-white" style="font-family: 'Cinzel', serif;">
                                <i class="fa-solid fa-chess-knight text-[var(--green)] mr-2"></i>Match Lobby
                            </h2>
                            <p class="text-sm text-[var(--muted)] mb-4">Enter your name and join the arena.</p>
                            <div class="flex gap-2 mb-3">
                                <input type="text" id="name-input" maxlength="24" placeholder="Your name"
                                       class="w-full bg-[var(--bg)] border border-[var(--line)] text-white p-3 rounded-lg text-sm focus:outline-none focus:border-[var(--green)]">
                            </div>
                            <button id="join-btn" class="w-full bg-[var(--green)] text-white font-extrabold px-4 py-3 rounded-lg text-sm transition hover:bg-[#a3d160] shadow-lg uppercase tracking-wider">
                                Join Match
                            </button>
                        </div>
                    </div>
                </div>

                <div id="game-over-overlay" class="overlay hidden">
                    <div class="bg-[var(--panel)] border border-[var(--line)] p-6 rounded-2xl text-center max-w-[92%] shadow-2xl w-[420px]">
                        <h2 class="text-2xl font-bold mb-2 text-white" style="font-family: 'Cinzel', serif;"><i class="fa-solid fa-flag text-red-400 mr-2"></i>Game Over</h2>
                        <p id="game-over-text" class="text-base text-[var(--muted)] mb-6 mt-3 leading-relaxed">The game has ended.</p>
                        <button onclick="window.location.reload()" class="bg-[var(--green)] hover:bg-[#a3d160] text-white font-extrabold px-4 py-3 rounded-lg text-sm transition w-full shadow-lg uppercase tracking-wider">Play Again</button>
                    </div>
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
                <div class="text-xs font-mono font-bold bg-[var(--green)] text-white px-3 py-2 rounded shrink-0 shadow-lg" id="my-status">Thinking</div>
            </div>
        </div>
    </div>

    <!-- RIGHT: Your Grimoire + Log -->
    <div class="w-full lg:w-[380px] xl:w-[420px] grimoire-container flex flex-col z-10 lg:h-screen lg:overflow-y-auto lg:sticky top-0 pb-6 lg:pb-0">
        <div class="p-5 border-b border-[var(--line)] bg-[var(--panel)] sticky top-0 z-20 flex justify-between items-center shadow-md">
            <h3 class="font-bold text-sm text-white uppercase tracking-widest flex items-center" style="font-family: 'Cinzel', serif;">
                <i class="fa-solid fa-book-journal-whills mr-2 text-[var(--green)]"></i>Your Grimoire
            </h3>
            <div id="turn-indicator" class="text-[10px] font-bold px-2 py-1 rounded bg-[var(--bg)] text-[var(--muted)] border border-[var(--line)]">WAITING</div>
        </div>

        <div id="spells-container" class="grid grid-cols-2 gap-3 p-4"></div>

        <div class="px-5 py-3 mt-auto border-t border-[var(--line)] flex justify-between items-center bg-[var(--panel)]">
            <span class="font-bold text-xs text-[var(--muted)] uppercase tracking-widest"><i class="fa-solid fa-list-ul mr-2"></i>Match Log</span>
            <button id="resign-btn" class="text-xs text-red-400 hover:text-red-300 transition font-bold">
                <i class="fa-solid fa-flag mr-1"></i>Resign
            </button>
        </div>
        <div class="flex-grow max-h-[250px] lg:max-h-[none] overflow-y-auto p-4 font-mono text-sm shadow-inner" id="move-history"></div>
    </div>
</div>

<script>
const socket = io();
const game = new Chess();

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

let myColor = null;
let myHand = [];
let usedSpells = new Set();
let oppHand = [];
let oppUsedSpells = new Set();
let gameReady = false;
let selectedSquare = null;
let activeSpell = null;
let spellSourceSq = null;
let moveNum = 1;
let playerName = localStorage.getItem("wizard_chess_name") || "";
let pendingJoin = false;
let historyLen = 1; // Track global history for Time-Turner checks

const bgMusic = document.getElementById("bgMusic");
const musicToggle = document.getElementById("music-toggle");
let musicEnabled = false;

const sounds = {
    move: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3"),
    capture: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3"),
    spell: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3"),
    start: new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/game-start.mp3"),
};

function setMusicButton() {
    musicToggle.textContent = bgMusic.paused ? "♫ Music Off" : "♫ Music On";
}

async function startMusic() {
    if (!bgMusic.paused) {
        musicEnabled = true;
        setMusicButton();
        return;
    }
    try {
        bgMusic.volume = 0.25;
        await bgMusic.play();
        musicEnabled = true;
    } catch (e) {
        musicEnabled = false;
    }
    setMusicButton();
}

function toggleMusic() {
    if (bgMusic.paused) {
        startMusic();
    } else {
        bgMusic.pause();
        musicEnabled = false;
        setMusicButton();
    }
}

musicToggle.addEventListener("click", toggleMusic);
setMusicButton();

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

function setMoveLogFromSan(text, color, isSpell = false) {
    const history = document.getElementById("move-history");
    const safeText = (text || "").toString();
    const style = isSpell ? "text-[var(--green)] font-bold" : "text-[#e3e3e3]";
    const icon = isSpell ? '<i class="fa-solid fa-wand-magic-sparkles text-[10px] mr-1 text-[var(--green)]"></i>' : "";

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

    const isCheck = game.in_check();
    const turnColor = game.turn();

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

            // RED KING LOGIC (Checkmate Warning Glow)
            let isKingInCheck = (p && p.type === 'k' && p.color === turnColor && isCheck);

            if (sq === selectedSquare || sq === spellSourceSq) {
                hlEl.className = "sq-selected";
                hlEl.style.display = "block";
            } else if (isKingInCheck) {
                hlEl.className = "sq-check";
                hlEl.style.display = "block";
            } else {
                hlEl.className = "sq-highlight";
                hlEl.style.display = "none";
            }

            dotEl.style.display = "none";

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
        if (activeSpell) {
            turnIndicator.innerText = `TARGET: ${activeSpell.name.toUpperCase()}`;
            turnIndicator.className = "text-[10px] font-bold px-2 py-1 rounded shadow bg-[var(--green)] text-white animate-pulse cursor-pointer";
            turnIndicator.onclick = cancelSpell;
        } else {
            turnIndicator.innerText = isMy ? "YOUR TURN" : "OPPONENT'S TURN";
            turnIndicator.className = `text-[10px] font-bold px-2 py-1 rounded shadow border ${isMy ? "bg-[var(--green)] text-white border-transparent" : "bg-[var(--bg)] text-[var(--muted)] border-[var(--line)]"}`;
            turnIndicator.onclick = null;
        }

        myStatus.innerText = isMy ? "Thinking" : "Waiting";
        myStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow-lg ${isMy ? "bg-[var(--green)] text-white" : "bg-[var(--bg)] text-[var(--muted)] border border-[var(--line)]"}`;

        oppStatus.innerText = !isMy ? "Thinking" : "Waiting";
        oppStatus.className = `text-xs font-mono font-bold px-3 py-2 rounded shadow border ${!isMy ? "bg-[var(--green)] text-white border-transparent" : "bg-[var(--bg)] text-[var(--muted)] border-[var(--line)]"}`;
    }

    // Your spells (right)
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
                <div class="text-[9px] lg:text-[10px] text-[var(--muted)] leading-snug text-center px-1 mt-1 font-medium">${spell.desc}</div>
            `;

            card.onclick = () => {
                if (isUsed || !gameReady || game.turn() !== myColor) return;

                if (isActive) {
                    cancelSpell();
                    return;
                }
                
                // EDGE CASE FIX: Prevent casting Time-Turner if history is too short
                if (spell.id === "time" && historyLen < 3) {
                    const turnInd = document.getElementById("turn-indicator");
                    turnInd.innerText = "NOT ENOUGH HISTORY";
                    turnInd.className = "text-[10px] font-bold px-2 py-1 rounded shadow bg-red-500 text-white animate-pulse";
                    setTimeout(cancelSpell, 1500);
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
                updateUI();
            };

            handContainer.appendChild(card);
        });
    }

    // OPPONENT'S GRIMOIRE (LEFT - VIEW ONLY, with descriptions, cannot interact)
    const oppContainer = document.getElementById("opp-spells-container");
    if (oppContainer && oppHand && oppHand.length > 0) {
        oppContainer.innerHTML = "";
        oppHand.forEach(spell => {
            const isUsed = oppUsedSpells.has(spell.id);

            const card = document.createElement("div");
            card.className = `spell-card p-2 lg:p-3 flex flex-col items-center justify-start ${isUsed ? "used" : ""} opacity-90`;
            card.style.setProperty("--spell-color", spell.color);
            card.style.setProperty("--spell-glow", spell.color + "33"); // weaker glow for view-only

            card.innerHTML = `
                <div class="w-10 h-10 lg:w-12 lg:h-12 mb-1.5 relative drop-shadow-[0_0_4px_${spell.color}66]">
                    ${spell.image}
                </div>
                <div class="text-[10px] lg:text-[11px] font-black tracking-wider uppercase mb-0.5 text-white text-center border-b pb-0.5 w-full" style="border-color:${spell.color}55; font-family: 'Cinzel', serif;">${spell.name}</div>
                <div class="text-[8px] lg:text-[9px] text-[var(--muted)] leading-snug text-center px-1 font-medium">${spell.desc}</div>
            `;
            // No onclick - view only, cannot mess with opponent's spells
            oppContainer.appendChild(card);
        });
    }

    calcMaterial();
}

function cancelSpell() {
    activeSpell = null;
    spellSourceSq = null;
    selectedSquare = null;
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

function switchTurnInFen(fen) {
    const parts = fen.split(" ");
    if (parts.length > 1) parts[1] = parts[1] === "w" ? "b" : "w";
    if (parts.length > 3) parts[3] = "-";
    return parts.join(" ");
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
                    // EDGE CASE FIX: Do not drop pawns on ranks 1 or 8 (Crashes FEN)
                    const targetRank = parseInt(sq[1], 10);
                    if (targetRank === 1 || targetRank === 8) {
                        temp.put({ type: "n", color: opp }, sq);
                    } else {
                        temp.put({ type: "p", color: opp }, sq);
                    }
                }
                nextFen = temp.fen();
            }
            // The King is now completely immune to direct enemy spells (Avada/Sectum)
            break;

        case "bombarda":
            {
                const fileIdxB = sq.charCodeAt(0);
                const rankIdxB = parseInt(sq[1], 10);
                const blastRadius = [
                    sq,
                    String.fromCharCode(fileIdxB + 1) + rankIdxB,
                    String.fromCharCode(fileIdxB - 1) + rankIdxB,
                    String.fromCharCode(fileIdxB) + (rankIdxB + 1),
                    String.fromCharCode(fileIdxB) + (rankIdxB - 1)
                ];
                let destroyedSomething = false;
                blastRadius.forEach(targetSq => {
                    if (targetSq.charCodeAt(0) >= 97 && targetSq.charCodeAt(0) <= 104 && parseInt(targetSq[1],10) >= 1 && parseInt(targetSq[1],10) <= 8) {
                        const tp = temp.get(targetSq);
                        // Make Kings immune to explosive splash damage
                        if (tp && tp.type !== "k") {
                            temp.remove(targetSq);
                            destroyedSomething = true;
                        }
                    }
                });
                if (destroyedSomething) nextFen = temp.fen();
            }
            break;

        case "any":
            {
                const fileIdx = sq.charCodeAt(0);
                const rankIdx = parseInt(sq[1], 10);
                let destroyedSomething = false;
                for (let f = fileIdx - 1; f <= fileIdx + 1; f++) {
                    for (let r = rankIdx - 1; r <= rankIdx + 1; r++) {
                        if (f < 97 || f > 104 || r < 1 || r > 8) continue;
                        const targetSq = String.fromCharCode(f) + r;
                        const targetPiece = temp.get(targetSq);
                        // Make Kings immune to Fiendfyre area-of-effect
                        if (targetPiece && targetPiece.type !== "k") {
                            temp.remove(targetSq);
                            destroyedSomething = true;
                        }
                    }
                }
                nextFen = temp.fen(); // Always apply (even if nothing hit) so spell is used
            }
            break;

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

                if (activeSpell.id === "portkey" && p) return;
                if (activeSpell.id === "leviosa" && ((fDist > 1 || rDist > 1) || p)) return;
                if (activeSpell.id === "alohomora") {
                    const ownHalf = myColor === "w" ? parseInt(sq[1], 10) <= 4 : parseInt(sq[1], 10) >= 5;
                    if (!ownHalf || p) return;
                }

                // EDGE CASE FIX: Imperio FEN rules & validation
                if (activeSpell.id === "imperio") {
                    // Bypass strict chess.js move validation to prevent King safety blocks.
                    // We treat it as a free teleport for an enemy piece.
                    const sourcePiece = temp.get(source);
                    if (sourcePiece && sourcePiece.type === 'k') {
                         spellSourceSq = null;
                         updateUI();
                         return; // Cannot Imperio the King
                    }
                    temp.remove(source);
                    if (sourcePiece) temp.put(sourcePiece, sq);
                    nextFen = temp.fen();
                    logText = `IMPERIO: Relocated enemy piece`;
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
        // EDGE CASE FIX: Verify spell doesn't leave your OWN King in Check (unless it obliterates the enemy king entirely)
        if (activeSpell.id !== "time") {
            const fenKings = nextFen.split(" ")[0];
            if (fenKings.includes("K") && fenKings.includes("k")) {
                const checkTemp = new Chess();
                let fParts = nextFen.split(" ");
                fParts[1] = myColor; // Evaluate check rule for the caster
                const validLoad = checkTemp.load(fParts.join(" "));
                if (validLoad && checkTemp.in_check()) {
                    const turnInd = document.getElementById("turn-indicator");
                    turnInd.innerText = "MUST ESCAPE CHECK!";
                    turnInd.className = "text-[10px] font-bold px-2 py-1 rounded shadow bg-red-500 text-white animate-pulse";
                    setTimeout(cancelSpell, 1500);
                    return; // Abort emitting the spell
                }
            }
        }
    
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

document.getElementById("resign-btn").onclick = () => {
    if (!gameReady || !myColor || myColor === "s") return;
    socket.emit("resign", { room, player_id: playerId });
};

async function joinGame() {
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
    await startMusic();

    document.getElementById("lobby-content").innerHTML = `
        <div class="py-4">
            <div class="inline-block mb-4">
                <svg class="animate-spin h-10 w-10 text-[var(--green)] mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>
            <h2 class="text-xl font-bold mb-2 text-white" style="font-family: 'Cinzel', serif;">Waiting for Opponent...</h2>
            <p class="text-sm text-[var(--muted)]">Send this link to a friend to begin.</p>
            <div class="flex gap-2 mt-5 max-w-[300px] mx-auto">
                <input type="text" id="share-link-waiting" readonly value="${location.href}" class="w-full bg-[var(--bg)] border border-[var(--line)] text-[var(--muted)] p-2 rounded-lg text-xs font-mono focus:outline-none">
                <button onclick="copyWaitingLink()" class="bg-[var(--green)] hover:bg-[#a3d160] text-white font-extrabold px-3 rounded-lg text-sm transition shadow-lg">
                    <i class="fa-solid fa-copy"></i>
                </button>
            </div>
        </div>
    `;
    setMusicButton();
}

window.copyWaitingLink = async () => {
    const input = document.getElementById("share-link-waiting");
    input.select();
    try { await navigator.clipboard.writeText(input.value); } catch (e) {}
};

document.getElementById("join-btn")?.addEventListener("click", joinGame);
document.getElementById("name-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") joinGame();
});

socket.on("connect", () => {
    const saved = localStorage.getItem("wizard_chess_name");
    if (saved && document.getElementById("name-input")) {
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
    oppHand = data.opp_hand || [];
    oppUsedSpells = new Set(data.opp_used || []);

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

    if (data.snapshot) {
        historyLen = data.snapshot.history_len;
        if (data.snapshot.fen) {
            try { game.load(data.snapshot.fen); } catch(e){}
        }
    }

    setBoardOrientation();
    buildBoardDOM();
    updateUI();

    if (data.snapshot && data.snapshot.started) {
        document.getElementById("waiting-overlay").style.display = "none";
    }
});

socket.on("room_state", (state) => {
    if (state) historyLen = state.history_len;
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
    }
    if (myColor) {
        const oppCol = myColor === "w" ? "b" : (myColor === "b" ? "w" : null);
        if (oppCol && data.used[oppCol]) {
            oppUsedSpells = new Set(data.used[oppCol]);
        }
    }
    updateUI();
});

socket.on("board_update", (data) => {
    if (data.room_state) historyLen = data.room_state.history_len;
    const isMyNormalMove = (data.color === myColor && !data.is_spell);

    if (!isMyNormalMove) {
        if (data.fen) {
            try { game.load(data.fen); } catch(e){}
        }
        updateUI();

        requestAnimationFrame(() => {
            setTimeout(() => {
                if (data.is_spell) sounds.spell.play().catch(() => {});
                else if ((data.san || "").includes("x")) sounds.capture.play().catch(() => {});
                else sounds.move.play().catch(() => {});
            }, 30);
        });

        if (data.san) {
            setMoveLogFromSan(data.san, data.color, !!data.is_spell);
        }
    } else {
        if (data.fen && game.fen() !== data.fen) {
            try { game.load(data.fen); } catch(e){}
        }
        updateUI();
    }

    if (data.is_spell && data.color === myColor && data.used_spell_id) {
        usedSpells.add(data.used_spell_id);
    }

    if (data.room_state && data.room_state.started) {
        document.getElementById("waiting-overlay").style.display = "none";
        gameReady = true;
    }

    // Standard Checkmate evaluation by the mover
    if (data.color === myColor && !data.room_state.game_over) {
        if (game.in_checkmate()) {
            const winner = game.turn() === 'w' ? 'b' : 'w';
            const winnerColor = winner === 'w' ? 'White' : 'Black';
            socket.emit("claim_win", {
                room, player_id: playerId, winner,
                reason: `Checkmate! A brilliant tactical hex! ${winnerColor} claims the House Cup!`
            });
        } else if (game.in_draw() || game.in_stalemate() || game.in_threefold_repetition()) {
            socket.emit("claim_win", {
                room, player_id: playerId, winner: "draw",
                reason: "Draw! A stalemate as stubborn as a Troll in the dungeons."
            });
        }
    }
});

socket.on("game_over", (data) => {
    const overlay = document.getElementById("game-over-overlay");
    const text = document.getElementById("game-over-text");
    overlay.classList.remove("hidden");
    const youWon = (data.winner === myColor);
    
    let displayReason = data.reason || "The game has ended.";
    
    let headerHtml = "";
    if (data.winner === "draw") {
        headerHtml = `<i class="fa-solid fa-handshake text-yellow-400 mr-2"></i>Draw!`;
    } else if (youWon) {
        headerHtml = `<i class="fa-solid fa-bolt text-yellow-400 mr-2"></i>Victory!`;
    } else if (myColor !== "s") {
        headerHtml = `<i class="fa-solid fa-skull text-red-500 mr-2"></i>Defeat!`;
    } else {
        headerHtml = `<i class="fa-solid fa-flag text-red-400 mr-2"></i>Game Over`;
    }
    
    overlay.querySelector('h2').innerHTML = headerHtml;
    text.innerHTML = `<span class="block text-white font-semibold mb-2" style="font-family: 'Cinzel', serif; font-size: 1.1rem;">${displayReason}</span>`;
    
    gameReady = false;
    updateUI();
});

buildBoardDOM();
updateUI();

if (playerName) {
    const nInput = document.getElementById("name-input");
    if (nInput) nInput.value = playerName;
}
</script>
</body>
</html>
'''

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"> SERVER ONLINE. PORT: {port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
