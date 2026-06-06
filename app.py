import os
import random
import secrets
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "lumos_maxima_secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

START_FEN = "rn1qkbnr/ppp1pppp/8/3p4/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 2"

SPELLS = [
    {"id": "avada", "name": "Avada Kedavra", "rarity": "Legendary", "icon": "⚡", "action": "click", "desc": "Click an enemy piece to destroy it."},
    {"id": "time", "name": "Time-Turner", "rarity": "Legendary", "icon": "⏳", "action": "instant", "desc": "Rewind the board to the previous round."},
    {"id": "imperio", "name": "Imperio", "rarity": "Rare", "icon": "👁️", "action": "drag", "desc": "Drag an enemy piece to make a legal move for them."},
    {"id": "sectum", "name": "Sectumsempra", "rarity": "Rare", "icon": "🩸", "action": "click", "desc": "Click an enemy piece to demote it to a Pawn."},
    {"id": "fiendfyre", "name": "Fiendfyre", "rarity": "Rare", "icon": "🔥", "action": "click", "desc": "Click a square to destroy it and its surrounding 8 squares."},
    {"id": "accio", "name": "Accio", "rarity": "Common", "icon": "🧲", "action": "drag", "desc": "Drag one of your pieces up to 2 squares in any direction."},
    {"id": "leviosa", "name": "Wingardium Leviosa", "rarity": "Common", "icon": "🪶", "action": "drag", "desc": "Drag one of your pieces to any adjacent empty square."},
    {"id": "alohomora", "name": "Alohomora", "rarity": "Common", "icon": "🗝️", "action": "drag", "desc": "Drag one of your pieces to any empty square on your half."},
    {"id": "expelliarmus", "name": "Expelliarmus", "rarity": "Common", "icon": "🪄", "action": "instant", "desc": "You keep the move and get another turn."},
    {"id": "protego", "name": "Protego", "rarity": "Common", "icon": "🛡️", "action": "click", "desc": "Click one of your Pawns to promote it to a Knight."},
]

ROOMS = {}   # room_id -> room state
SID_ROOM = {}  # request.sid -> room_id


def opponent(color):
    return "b" if color == "w" else "w"


def new_hand():
    legendary = [s for s in SPELLS if s["rarity"] == "Legendary"]
    rare = [s for s in SPELLS if s["rarity"] == "Rare"]
    common = [s for s in SPELLS if s["rarity"] == "Common"]

    hand = random.sample(legendary, 1) + random.sample(rare, 2) + random.sample(common, 3)
    random.shuffle(hand)
    return hand


def get_room(room_id):
    if room_id not in ROOMS:
        ROOMS[room_id] = {
            "fen": START_FEN,
            "turn": "w",
            "players": {"w": None, "b": None},
            "sid_color": {},
            "hands": {},
            "used": {"w": set(), "b": set()},
            "connected": 0,
            "started": False,
        }
    return ROOMS[room_id]


def snapshot(room_id):
    room = ROOMS[room_id]
    return {
        "room": room_id,
        "fen": room["fen"],
        "turn": room["turn"],
        "connected": room["connected"],
        "white_connected": room["players"]["w"] is not None,
        "black_connected": room["players"]["b"] is not None,
        "started": room["players"]["w"] is not None and room["players"]["b"] is not None,
    }


@app.route("/")
def index():
    return render_template_string(HTML_PAYLOAD)


@socketio.on("join_room")
def handle_join(data):
    room_id = data["room"] if isinstance(data, dict) else str(data)
    room = get_room(room_id)

    if room["players"]["w"] is None:
        color = "w"
    elif room["players"]["b"] is None:
        color = "b"
    else:
        color = "s"  # spectator

    join_room(room_id)
    SID_ROOM[request.sid] = room_id

    if color in ("w", "b"):
        room["players"][color] = request.sid
        room["sid_color"][request.sid] = color
        room["hands"][request.sid] = new_hand()
        room["connected"] = sum(1 for x in room["players"].values() if x is not None)
    else:
        room["connected"] = sum(1 for x in room["players"].values() if x is not None)

    emit(
        "role_assigned",
        {
            "color": color,
            "hand": room["hands"].get(request.sid, []),
            "snapshot": snapshot(room_id),
        },
        to=request.sid,
    )

    emit("room_state", snapshot(room_id), room=room_id)
    if room["players"]["w"] is not None and room["players"]["b"] is not None:
        room["started"] = True
        emit("game_ready", snapshot(room_id), room=room_id)


@socketio.on("standard_move")
def handle_standard_move(data):
    room_id = SID_ROOM.get(request.sid)
    if not room_id:
        return

    room = ROOMS.get(room_id)
    if not room:
        return

    color = room["sid_color"].get(request.sid)
    if color not in ("w", "b"):
        return

    if room["turn"] != color:
        emit(
            "action_denied",
            {"reason": "It is not your turn.", "snapshot": snapshot(room_id)},
            to=request.sid,
        )
        return

    room["fen"] = data["fen"]
    room["turn"] = opponent(color)

    emit(
        "standard_move",
        {
            "from": data.get("from"),
            "to": data.get("to"),
            "san": data.get("san"),
            "color": color,
            "fen": room["fen"],
            "turn": room["turn"],
        },
        room=room_id,
        include_self=False,
    )


@socketio.on("spell_effect")
def handle_spell_effect(data):
    room_id = SID_ROOM.get(request.sid)
    if not room_id:
        return

    room = ROOMS.get(room_id)
    if not room:
        return

    color = room["sid_color"].get(request.sid)
    if color not in ("w", "b"):
        return

    spell_id = data.get("spell_id")
    consume_turn = bool(data.get("consume_turn", True))
    if spell_id in room["used"][color]:
        emit(
            "action_denied",
            {"reason": "That spell was already used.", "snapshot": snapshot(room_id)},
            to=request.sid,
        )
        return

    if room["turn"] != color:
        emit(
            "action_denied",
            {"reason": "It is not your turn.", "snapshot": snapshot(room_id)},
            to=request.sid,
        )
        return

    room["used"][color].add(spell_id)
    room["fen"] = data.get("fen", room["fen"])
    if consume_turn:
        room["turn"] = opponent(color)

    emit(
        "spell_effect",
        {
            "spell_id": spell_id,
            "name": data.get("name", spell_id),
            "fen": room["fen"],
            "consume_turn": consume_turn,
            "color": color,
            "turn": room["turn"],
        },
        room=room_id,
        include_self=False,
    )


@socketio.on("disconnect")
def handle_disconnect():
    room_id = SID_ROOM.pop(request.sid, None)
    if not room_id:
        return

    room = ROOMS.get(room_id)
    if not room:
        return

    color = room["sid_color"].pop(request.sid, None)
    room["hands"].pop(request.sid, None)

    if color in ("w", "b") and room["players"].get(color) == request.sid:
        room["players"][color] = None

    room["connected"] = sum(1 for x in room["players"].values() if x is not None)

    try:
        leave_room(room_id)
    except Exception:
        pass

    emit("room_state", snapshot(room_id), room=room_id)

    if room["connected"] == 0:
        ROOMS.pop(room_id, None)


HTML_PAYLOAD = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Wizard's Chess</title>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>

    <style>
        :root{
            --bg:#1f1f1f;
            --panel:#262522;
            --panel-2:#2d2b28;
            --panel-3:#31302d;
            --text:#f5f5f5;
            --muted:#a3a3a3;
            --accent:#81b64c;
            --accent-2:#9dd85a;
            --border:#3d3b37;
            --gold:#f1b24a;
            --purple:#a855f7;
            --silver:#b7b7b3;
            --glow:rgba(168,85,247,.35);
            --white-square:#eeeed2;
            --black-square:#769656;
        }

        *{box-sizing:border-box}
        body{
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
            background:linear-gradient(180deg,#191919 0%, #23211f 100%);
            color:var(--text);
            min-height:100vh;
        }

        .topbar{
            height:64px;
            display:flex;
            align-items:center;
            justify-content:space-between;
            padding:0 18px;
            background:#151413;
            border-bottom:1px solid #000;
            box-shadow:0 4px 18px rgba(0,0,0,.28);
            position:sticky;
            top:0;
            z-index:20;
        }

        .brand{
            display:flex;
            align-items:center;
            gap:10px;
            font-weight:800;
            letter-spacing:.2px;
            font-size:1.15rem;
        }
        .brand-badge{
            width:34px;height:34px;border-radius:10px;
            background:linear-gradient(135deg,var(--accent),#5f8f33);
            display:grid;place-items:center;
            color:#121212;
            box-shadow:0 8px 18px rgba(129,182,76,.18);
        }
        .top-actions{
            display:flex;align-items:center;gap:10px;
        }
        .status-pill{
            padding:8px 12px;
            border:1px solid var(--border);
            background:#201f1c;
            border-radius:999px;
            color:var(--muted);
            font-size:.92rem;
        }
        .info-btn{
            width:36px;height:36px;border-radius:50%;
            border:1px solid var(--border);
            background:#25231f;
            color:#fff;
            cursor:pointer;
            font-weight:800;
        }

        .page{
            width:min(1400px,100%);
            margin:0 auto;
            padding:20px;
        }

        .layout{
            display:grid;
            grid-template-columns:minmax(340px, 1fr) 370px;
            gap:20px;
            align-items:start;
        }

        .board-panel{
            background:transparent;
        }

        .player-strip{
            background:var(--panel);
            border:1px solid var(--border);
            border-radius:16px 16px 0 0;
            padding:12px 14px;
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:12px;
        }
        .player-left{
            display:flex;align-items:center;gap:10px;min-width:0;
        }
        .avatar{
            width:38px;height:38px;border-radius:10px;
            display:grid;place-items:center;
            font-weight:800;
            background:#45423c;
            color:#fff;
            flex:0 0 auto;
        }
        .avatar.green{background:var(--accent); color:#111}
        .player-name{
            font-weight:700;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        }
        .player-sub{
            font-size:.82rem;color:var(--muted);margin-top:2px;
        }
        .clock{
            min-width:94px;
            text-align:center;
            padding:9px 12px;
            border-radius:10px;
            background:#171614;
            border:1px solid #40403c;
            font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
            font-weight:800;
            letter-spacing:.3px;
        }
        .clock.active{
            background:#f7f7f7;
            color:#111;
            border-color:#f7f7f7;
        }

        .captured{
            background:var(--panel);
            border-left:1px solid var(--border);
            border-right:1px solid var(--border);
            padding:8px 14px 12px;
            min-height:34px;
            display:flex;
            align-items:center;
            flex-wrap:wrap;
            gap:6px;
        }
        .captured-piece{
            width:22px;height:22px;
            border-radius:4px;
            background-size:contain;
            background-repeat:no-repeat;
            background-position:center;
            opacity:.96;
        }
        .material-adv{
            margin-left:8px;
            color:var(--muted);
            font-weight:700;
            font-size:.84rem;
        }

        .board-wrap{
            border:1px solid var(--border);
            border-top:none;
            background:#111;
            border-radius:0 0 16px 16px;
            padding:12px;
            box-shadow:0 18px 30px rgba(0,0,0,.28);
        }
        .board-shell{
            border-radius:12px;
            overflow:hidden;
            box-shadow:0 0 0 1px rgba(255,255,255,.04), 0 18px 40px rgba(0,0,0,.35);
        }
        .board-shell.magic-active{
            box-shadow:0 0 0 1px rgba(168,85,247,.5), 0 0 30px var(--glow), 0 18px 40px rgba(0,0,0,.35);
            cursor:crosshair;
        }

        #board{
            width:100%;
        }

        .white-1e1d7 { background-color: var(--white-square) !important; }
        .black-3c85d { background-color: var(--black-square) !important; }
        .board-b72b1{
            border:none !important;
        }

        .spell-banner{
            display:none;
            margin-top:12px;
            background:linear-gradient(135deg,#7c3aed,#a855f7);
            border:1px solid rgba(255,255,255,.08);
            border-radius:12px;
            padding:12px 14px;
            font-weight:800;
            box-shadow:0 10px 24px rgba(0,0,0,.22);
        }

        .hand-panel{
            margin-top:12px;
            background:var(--panel);
            border:1px solid var(--border);
            border-radius:16px;
            padding:14px;
            box-shadow:0 12px 25px rgba(0,0,0,.2);
        }
        .hand-head{
            display:flex;
            align-items:center;
            justify-content:space-between;
            margin-bottom:12px;
        }
        .hand-title{
            font-size:.82rem;
            text-transform:uppercase;
            letter-spacing:.15em;
            color:var(--muted);
            font-weight:800;
        }
        .hand-note{
            color:var(--muted);
            font-size:.82rem;
        }
        .spells-row{
            display:flex;
            gap:10px;
            overflow-x:auto;
            padding-bottom:4px;
        }
        .spell-card{
            min-width:96px;
            width:96px;
            height:128px;
            border-radius:14px;
            border:1px solid var(--border);
            background:linear-gradient(180deg,#312f2b 0%, #24221f 100%);
            cursor:pointer;
            padding:10px 8px;
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:flex-start;
            text-align:center;
            transition:transform .15s ease, border-color .15s ease, box-shadow .15s ease, opacity .15s ease;
            position:relative;
        }
        .spell-card:hover{
            transform:translateY(-3px);
            border-color:#64615b;
            box-shadow:0 8px 18px rgba(0,0,0,.25);
        }
        .spell-card.used{
            opacity:.18;
            pointer-events:none;
            filter:grayscale(100%);
        }
        .spell-card.Legendary{ border-bottom:4px solid var(--gold); }
        .spell-card.Rare{ border-bottom:4px solid var(--purple); }
        .spell-card.Common{ border-bottom:4px solid var(--silver); }

        .spell-icon{
            font-size:1.7rem;
            margin-top:8px;
            margin-bottom:10px;
            text-shadow:0 2px 4px rgba(0,0,0,.35);
        }
        .spell-name{
            font-size:.74rem;
            font-weight:800;
            line-height:1.1;
        }
        .spell-desc{
            margin-top:6px;
            font-size:.68rem;
            color:var(--muted);
            line-height:1.2;
        }

        .sidebar{
            display:flex;
            flex-direction:column;
            gap:12px;
        }
        .sidebar-card{
            background:var(--panel);
            border:1px solid var(--border);
            border-radius:16px;
            overflow:hidden;
            box-shadow:0 12px 25px rgba(0,0,0,.18);
        }
        .sidebar-header{
            padding:14px 16px;
            background:#211f1c;
            border-bottom:1px solid var(--border);
            display:flex;
            align-items:center;
            justify-content:space-between;
        }
        .sidebar-title{
            font-weight:800;
            font-size:.9rem;
            letter-spacing:.03em;
        }
        .sidebar-body{
            padding:0;
            max-height:560px;
            overflow:auto;
        }

        .move-history{
            display:grid;
            grid-template-columns:42px 1fr 1fr;
            font-size:.94rem;
            font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
        }
        .move-row{ display:contents; }
        .move-row > div{
            padding:10px 12px;
            border-bottom:1px solid var(--border);
        }
        .move-num{
            background:#201e1b;
            color:var(--muted);
            text-align:right;
        }
        .move-ply{
            font-weight:700;
            color:#f1f1f1;
        }
        .spell-ply{
            grid-column:span 2;
            color:#c9a3ff;
            background:#241b2d;
            font-weight:800;
        }

        .lobby{
            padding:16px;
            display:flex;
            flex-direction:column;
            gap:10px;
        }
        .lobby input{
            width:100%;
            border-radius:10px;
            border:1px solid var(--border);
            background:#141312;
            color:#fff;
            padding:12px 12px;
            font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
            font-size:.9rem;
        }
        .btn{
            width:100%;
            border:none;
            border-radius:10px;
            padding:12px 14px;
            background:var(--accent);
            color:#101010;
            font-weight:900;
            cursor:pointer;
            text-transform:uppercase;
            letter-spacing:.02em;
        }
        .btn:hover{ background:var(--accent-2); }

        .mini-state{
            padding:16px;
            color:var(--muted);
            line-height:1.45;
            font-size:.95rem;
        }

        .notification{
            position:fixed;
            left:50%;
            top:90px;
            transform:translateX(-50%);
            background:rgba(16,16,16,.92);
            color:#fff;
            border:1px solid rgba(168,85,247,.6);
            border-radius:12px;
            padding:12px 16px;
            z-index:200;
            display:none;
            box-shadow:0 0 30px var(--glow);
            font-weight:800;
            max-width:min(92vw, 640px);
            text-align:center;
        }

        .modal-overlay{
            position:fixed;
            inset:0;
            display:none;
            justify-content:center;
            align-items:center;
            background:rgba(0,0,0,.82);
            z-index:300;
            padding:20px;
        }
        .modal{
            width:min(760px, 100%);
            max-height:88vh;
            overflow:auto;
            background:#1f1d1b;
            border:1px solid var(--border);
            border-radius:18px;
            box-shadow:0 24px 60px rgba(0,0,0,.5);
            padding:22px;
        }
        .modal h2{ margin:0 0 10px 0; }
        .modal p{ color:#d8d8d8; line-height:1.55; }
        .grimoire{
            display:grid;
            grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));
            gap:12px;
            margin-top:14px;
        }
        .spell-row-item{
            background:#24221f;
            border:1px solid var(--border);
            border-radius:14px;
            padding:12px;
        }
        .spell-row-item h4{ margin:0 0 6px 0; }
        .spell-row-item p{ margin:0; font-size:.92rem; color:#cfcfcf; }

        @media (max-width: 1080px){
            .layout{ grid-template-columns:1fr; }
            .sidebar-body{ max-height:none; }
        }
    </style>
</head>
<body>
    <div class="topbar">
        <div class="brand">
            <div class="brand-badge">♞</div>
            <div>Wizard's Chess</div>
        </div>
        <div class="top-actions">
            <div class="status-pill" id="status-pill">Connecting…</div>
            <button class="info-btn" id="help-btn">i</button>
        </div>
    </div>

    <div class="notification" id="notification"></div>

    <div class="page">
        <div class="layout">
            <div class="board-panel">
                <div class="player-strip">
                    <div class="player-left">
                        <div class="avatar" id="opp-avatar">P2</div>
                        <div>
                            <div class="player-name" id="opp-name">Opponent</div>
                            <div class="player-sub" id="opp-sub">Waiting for a challenger…</div>
                        </div>
                    </div>
                    <div class="clock" id="clock-opp">10:00</div>
                </div>

                <div class="captured" id="opp-captured"></div>

                <div class="board-wrap">
                    <div class="board-shell" id="board-shell">
                        <div id="board"></div>
                    </div>
                    <div class="spell-banner" id="spell-banner"></div>
                </div>

                <div class="captured" id="my-captured" style="border-radius:0 0 16px 16px;border-top:none;"></div>

                <div class="player-strip" style="border-radius:0 0 16px 16px;border-top:none;">
                    <div class="player-left">
                        <div class="avatar green" id="my-avatar">P1</div>
                        <div>
                            <div class="player-name" id="my-name">You</div>
                            <div class="player-sub" id="my-sub">Get ready.</div>
                        </div>
                    </div>
                    <div class="clock active" id="clock-my">10:00</div>
                </div>

                <div class="hand-panel">
                    <div class="hand-head">
                        <div class="hand-title">Your Hand</div>
                        <div class="hand-note" id="hand-note">6 spells: 1 Legendary, 2 Rares, 3 Commons</div>
                    </div>
                    <div class="spells-row" id="spells-view"></div>
                </div>
            </div>

            <div class="sidebar">
                <div class="sidebar-card">
                    <div class="sidebar-header">
                        <div class="sidebar-title">Match Telemetry</div>
                        <div style="color:var(--muted);font-size:.82rem" id="room-tag">Room</div>
                    </div>
                    <div class="sidebar-body">
                        <div class="move-history" id="move-history"></div>
                    </div>
                </div>

                <div class="sidebar-card">
                    <div class="sidebar-header">
                        <div class="sidebar-title">Invite</div>
                        <div style="color:var(--muted);font-size:.82rem" id="state-tag">Waiting</div>
                    </div>
                    <div class="lobby" id="lobby-box">
                        <input type="text" id="shareLink" readonly />
                        <button class="btn" id="copy-btn">Copy Link</button>
                    </div>
                    <div class="mini-state" id="mini-state">
                        Share the link above to start a game. Once a second player joins, the board unlocks and both hands become live.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="rules-modal">
        <div class="modal">
            <h2>How Wizard's Chess Works</h2>
            <p>
                Each player receives exactly 6 spells: 1 Legendary, 2 Rare, and 3 Common.
                Targeted spells require the correct kind of click or drag, and the server only allows a spell when it is actually your turn.
            </p>
            <p>
                Expelliarmus does not end your turn. All other spells consume the turn after they resolve.
                Kings are never directly destroyed by spells.
            </p>

            <div class="grimoire">
                <div class="spell-row-item"><h4 style="color:var(--gold)">Avada Kedavra</h4><p>Click an enemy piece to destroy it.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--gold)">Time-Turner</h4><p>Rewind to the previous round.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--purple)">Imperio</h4><p>Force a legal move from an enemy piece.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--purple)">Sectumsempra</h4><p>Demote an enemy piece to a Pawn.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--purple)">Fiendfyre</h4><p>Destroy a target square and adjacent squares.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--silver)">Accio</h4><p>Move your piece up to 2 squares in any direction.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--silver)">Wingardium Leviosa</h4><p>Move your piece to any adjacent empty square.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--silver)">Alohomora</h4><p>Move your piece to any empty square on your half.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--silver)">Expelliarmus</h4><p>Skip the opponent's reply and move again.</p></div>
                <div class="spell-row-item"><h4 style="color:var(--silver)">Protego</h4><p>Promote one of your Pawns to a Knight.</p></div>
            </div>

            <div style="margin-top:18px">
                <button class="btn" id="close-help" style="max-width:220px;">Close Manual</button>
            </div>
        </div>
    </div>

    <script>
        const socket = io();

        const room = (() => {
            const p = new URLSearchParams(window.location.search);
            let r = p.get("room");
            if (!r) {
                r = Math.random().toString(36).slice(2, 9);
                const next = `${location.origin}${location.pathname}?room=${r}`;
                history.replaceState({}, "", next);
            }
            return r;
        })();

        document.getElementById("shareLink").value = window.location.href;
        document.getElementById("room-tag").textContent = `Room ${room}`;

        const sfxMove = new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3");
        const sfxCapture = new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3");
        const sfxStart = new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/game-start.mp3");
        const sfxSpell = new Audio("https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3");

        const game = new Chess();
        let board = null;
        let myColor = null;
        let activeSpell = null;
        let myHand = [];
        let fenHistory = [game.fen()];
        let moveNum = 1;
        let gameStarted = false;
        let lastSnapshot = null;

        function showPopup(msg) {
            const el = $("#notification");
            el.text(msg).stop(true, true).fadeIn(160);
            setTimeout(() => el.fadeOut(260), 2200);
        }

        function setStatus(text) {
            $("#status-pill").text(text);
            $("#state-tag").text(text);
        }

        function clearSpellMode() {
            activeSpell = null;
            $("#board-shell").removeClass("magic-active");
            $("#spell-banner").hide().text("");
        }

        function setTurnUI() {
            if (!myColor) return;
            const myTurn = game.turn() === myColor;
            $("#clock-my").toggleClass("active", myTurn);
            $("#clock-opp").toggleClass("active", !myTurn);

            if (game.game_over()) {
                setStatus("Game over");
                $("#my-sub").text("Game finished.");
                $("#opp-sub").text("Game finished.");
            } else if (!gameStarted) {
                setStatus("Waiting for opponent");
                $("#my-sub").text("Waiting for the second player.");
                $("#opp-sub").text("Waiting for the second player.");
            } else {
                setStatus(myTurn ? "Your turn" : "Opponent's turn");
                $("#my-sub").text(myTurn ? "You can move now." : "Waiting for the opponent.");
                $("#opp-sub").text(myTurn ? "Waiting for the opponent." : "Thinking…");
            }
        }

        function syncBoard(fen, pushHistory = true) {
            if (!fen) return;
            game.load(fen);
            board.position(fen);
            if (pushHistory && fenHistory[fenHistory.length - 1] !== fen) {
                fenHistory.push(fen);
            }
            updateCapturedPieces();
            setTurnUI();
        }

        function markUsed(spellId) {
            $(`#card-${spellId}`).addClass("used");
        }

        function appendSpellLog(text) {
            $("#move-history").append(
                `<div class="move-row"><div></div><div class="move-ply spell-ply">✨ ${text}</div></div>`
            );
            scrollTelemetry();
        }

        function appendMove(move) {
            const san = move.san || `${move.from}-${move.to}`;
            if (move.color === "w") {
                $("#move-history").append(
                    `<div class="move-row">
                        <div class="move-num">${moveNum}.</div>
                        <div class="move-ply">${san}</div>
                        <div class="move-ply"></div>
                    </div>`
                );
            } else {
                const lastRow = $("#move-history .move-row").last();
                if (lastRow.length && lastRow.find(".move-ply").eq(2).text().trim() === "") {
                    lastRow.find(".move-ply").eq(2).text(san);
                } else {
                    $("#move-history").append(
                        `<div class="move-row">
                            <div class="move-num">${moveNum}.</div>
                            <div class="move-ply"></div>
                            <div class="move-ply">${san}</div>
                        </div>`
                    );
                }
                moveNum += 1;
            }
            scrollTelemetry();
        }

        function scrollTelemetry() {
            const box = $(".sidebar-body")[0];
            if (box) box.scrollTop = box.scrollHeight;
        }

        function updateCapturedPieces() {
            const boardFen = game.fen().split(" ")[0];
            const counts = {
                w: { p: 0, n: 0, b: 0, r: 0, q: 0 },
                b: { p: 0, n: 0, b: 0, r: 0, q: 0 }
            };

            for (const ch of boardFen) {
                if (ch >= "a" && ch <= "z" && counts.b[ch] !== undefined) counts.b[ch]++;
                if (ch >= "A" && ch <= "Z") {
                    const p = ch.toLowerCase();
                    if (counts.w[p] !== undefined) counts.w[p]++;
                }
            }

            const base = { p: 8, n: 2, b: 2, r: 2, q: 1 };
            const values = { p: 1, n: 3, b: 3, r: 5, q: 9 };

            let capW = "";
            let capB = "";
            let wScore = 0;
            let bScore = 0;

            ["q", "r", "b", "n", "p"].forEach(p => {
                const wMissing = base[p] - counts.w[p];
                const bMissing = base[p] - counts.b[p];

                for (let i = 0; i < bMissing; i++) {
                    capW += `<div class="captured-piece" style="background-image:url('https://chessboardjs.com/img/chesspieces/wikipedia/b${p.toUpperCase()}.png')"></div>`;
                    wScore += values[p];
                }
                for (let i = 0; i < wMissing; i++) {
                    capB += `<div class="captured-piece" style="background-image:url('https://chessboardjs.com/img/chesspieces/wikipedia/w${p.toUpperCase()}.png')"></div>`;
                    bScore += values[p];
                }
            });

            const wAdv = wScore - bScore;
            const bAdv = bScore - wScore;

            if (wAdv > 0) capW += `<span class="material-adv">+${wAdv}</span>`;
            if (bAdv > 0) capB += `<span class="material-adv">+${bAdv}</span>`;

            if (myColor === "w") {
                $("#my-captured").html(capW);
                $("#opp-captured").html(capB);
            } else if (myColor === "b") {
                $("#my-captured").html(capB);
                $("#opp-captured").html(capW);
            }
        }

        function renderHand(hand) {
            $("#spells-view").empty();
            hand.forEach(spell => {
                const card = $(`
                    <div class="spell-card ${spell.rarity}" id="card-${spell.id}" title="${spell.desc}">
                        <div class="spell-icon">${spell.icon}</div>
                        <div class="spell-name">${spell.name}</div>
                        <div class="spell-desc">${spell.desc}</div>
                    </div>
                `);

                card.on("click", function () {
                    if (!myColor) return;
                    if (game.turn() !== myColor) {
                        showPopup("You can only cast spells on your turn.");
                        return;
                    }
                    if ($(this).hasClass("used")) return;

                    if (spell.id === "time") {
                        if (fenHistory.length < 3) {
                            showPopup("Not enough history to rewind yet.");
                            return;
                        }
                        markUsed(spell.id);
                        sfxSpell.play();
                        const rewindFen = fenHistory[fenHistory.length - 3];
                        game.load(rewindFen);
                        board.position(rewindFen);
                        fenHistory.push(rewindFen);
                        clearSpellMode();
                        appendSpellLog("TIME-TURNER");
                        updateCapturedPieces();
                        setTurnUI();
                        socket.emit("spell_effect", {
                            room: room,
                            spell_id: spell.id,
                            name: spell.name,
                            fen: rewindFen,
                            consume_turn: true
                        });
                        return;
                    }

                    if (spell.id === "expelliarmus") {
                        markUsed(spell.id);
                        sfxSpell.play();
                        clearSpellMode();
                        appendSpellLog("EXPELLIARMUS");
                        showPopup("Opponent skipped. You keep the move.");
                        socket.emit("spell_effect", {
                            room: room,
                            spell_id: spell.id,
                            name: spell.name,
                            fen: game.fen(),
                            consume_turn: false
                        });
                        return;
                    }

                    activeSpell = spell;
                    $("#board-shell").addClass("magic-active");
                    $("#spell-banner").text(`🪄 ${spell.name.toUpperCase()}: ${spell.desc}`).fadeIn(120);
                    showPopup(`${spell.name} armed.`);
                });

                $("#spells-view").append(card);
            });
        }

        function finishTargetedSpell(spell, extraLogText) {
            markUsed(spell.id);
            sfxSpell.play();
            appendSpellLog(extraLogText || spell.name.toUpperCase());
            updateCapturedPieces();
            setTurnUI();
            socket.emit("spell_effect", {
                room: room,
                spell_id: spell.id,
                name: spell.name,
                fen: game.fen(),
                consume_turn: true
            });
            clearSpellMode();
        }

        function isOnYourHalf(square) {
            const rank = parseInt(square[1], 10);
            return myColor === "w" ? rank <= 4 : rank >= 5;
        }

        function onDragStart(source, piece) {
            if (game.game_over()) return false;
            if (!myColor) return false;

            if (activeSpell) {
                if (activeSpell.action !== "drag") return false;
                if (activeSpell.id === "imperio") {
                    return piece.charAt(0) !== myColor;
                }
                return piece.charAt(0) === myColor;
            }

            if (game.turn() !== myColor) return false;
            if (piece.charAt(0) !== myColor) return false;
            return true;
        }

        function onDrop(source, target) {
            if (activeSpell && activeSpell.action === "drag") {
                const movingPiece = game.get(source);
                const targetPiece = game.get(target);

                if (!movingPiece) return "snapback";
                if (targetPiece && targetPiece.type === "k") return "snapback";

                const fileDist = Math.abs(source.charCodeAt(0) - target.charCodeAt(0));
                const rankDist = Math.abs(parseInt(source[1], 10) - parseInt(target[1], 10));

                if (activeSpell.id === "imperio") {
                    const originalFen = game.fen();
                    const forcedTurn = opponent(myColor);
                    const parts = originalFen.split(" ");
                    parts[1] = forcedTurn;
                    game.load(parts.join(" "));
                    const move = game.move({ from: source, to: target, promotion: "q" });
                    if (!move) {
                        game.load(originalFen);
                        return "snapback";
                    }
                    board.position(game.fen());
                    fenHistory.push(game.fen());
                    finishTargetedSpell(activeSpell, `IMPERIO: ${move.san}`);
                    return;
                }

                if (activeSpell.id === "accio") {
                    if (fileDist <= 2 && rankDist <= 2) {
                        game.remove(source);
                        game.put(movingPiece, target);
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, "ACCIO");
                        return;
                    }
                    return "snapback";
                }

                if (activeSpell.id === "leviosa") {
                    if (fileDist <= 1 && rankDist <= 1 && !targetPiece) {
                        game.remove(source);
                        game.put(movingPiece, target);
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, "WINGARDIUM LEVIOSA");
                        return;
                    }
                    return "snapback";
                }

                if (activeSpell.id === "alohomora") {
                    if (!targetPiece && isOnYourHalf(target)) {
                        game.remove(source);
                        game.put(movingPiece, target);
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, "ALOHOMORA");
                        return;
                    }
                    return "snapback";
                }

                return "snapback";
            }

            if (game.turn() !== myColor) return "snapback";

            const move = game.move({ from: source, to: target, promotion: "q" });
            if (move === null) return "snapback";

            board.position(game.fen());
            fenHistory.push(game.fen());
            if (move.flags && move.flags.indexOf("c") !== -1) sfxCapture.play();
            else sfxMove.play();

            appendMove(move);
            updateCapturedPieces();
            setTurnUI();

            socket.emit("standard_move", {
                room: room,
                from: source,
                to: target,
                san: move.san,
                color: move.color,
                fen: game.fen()
            });
        }

        function onSnapEnd() {
            board.position(game.fen());
        }

        function clickSpellTarget(square) {
            if (!activeSpell || activeSpell.action !== "click") return;

            const p = game.get(square);
            if (activeSpell.id === "avada") {
                if (p && p.color !== myColor && p.type !== "k") {
                    game.remove(square);
                    board.position(game.fen());
                    fenHistory.push(game.fen());
                    finishTargetedSpell(activeSpell, "AVADA KEDAVRA");
                } else {
                    showPopup("Click a non-King enemy piece.");
                }
                return;
            }

            if (activeSpell.id === "sectum") {
                if (p && p.color !== myColor && p.type !== "k") {
                    game.remove(square);
                    game.put({ type: "p", color: p.color }, square);
                    board.position(game.fen());
                    fenHistory.push(game.fen());
                    finishTargetedSpell(activeSpell, "SECTUMSEMPRA");
                } else {
                    showPopup("Click an enemy piece.");
                }
                return;
            }

            if (activeSpell.id === "fiendfyre") {
                const file = square.charCodeAt(0);
                const rank = parseInt(square[1], 10);
                for (let f = file - 1; f <= file + 1; f++) {
                    for (let r = rank - 1; r <= rank + 1; r++) {
                        const sq = String.fromCharCode(f) + String(r);
                        const t = game.get(sq);
                        if (t && t.type !== "k") game.remove(sq);
                    }
                }
                board.position(game.fen());
                fenHistory.push(game.fen());
                finishTargetedSpell(activeSpell, "FIENDFYRE");
                return;
            }

            if (activeSpell.id === "protego") {
                if (p && p.color === myColor && p.type === "p") {
                    game.remove(square);
                    game.put({ type: "n", color: myColor }, square);
                    board.position(game.fen());
                    fenHistory.push(game.fen());
                    finishTargetedSpell(activeSpell, "PROTEGO");
                } else {
                    showPopup("Click one of your Pawns.");
                }
                return;
            }
        }

        board = Chessboard("board", {
            draggable: true,
            position: "start",
            orientation: "white",
            pieceTheme: "https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png",
            onDragStart: onDragStart,
            onDrop: onDrop,
            onSnapEnd: onSnapEnd
        });

        $(window).on("resize", function () {
            if (board && board.resize) board.resize();
        });

        $("#board").on("click", ".square-55d63", function () {
            const square = $(this).attr("data-square");
            clickSpellTarget(square);
        });

        $("#help-btn").on("click", function () {
            $("#rules-modal").css("display", "flex");
        });

        $("#close-help").on("click", function () {
            $("#rules-modal").hide();
        });

        $("#copy-btn").on("click", async function () {
            try {
                await navigator.clipboard.writeText(document.getElementById("shareLink").value);
                $(this).text("Copied!");
                setTimeout(() => $(this).text("Copy Link"), 1500);
            } catch (e) {
                const input = document.getElementById("shareLink");
                input.select();
                document.execCommand("copy");
                $(this).text("Copied!");
                setTimeout(() => $(this).text("Copy Link"), 1500);
            }
        });

        function applyRoomState(state) {
            lastSnapshot = state;
            $("#room-tag").text(`Room ${state.room}`);
            gameStarted = !!state.started;

            if (state.white_connected && state.black_connected) {
                $("#lobby-box").slideUp(180);
                $("#mini-state").text("Both players connected. The game is live.");
            } else {
                $("#lobby-box").slideDown(0);
                $("#mini-state").text("Waiting for another player to join.");
            }

            setTurnUI();
        }

        socket.on("connect", function () {
            setStatus("Joining room…");
            socket.emit("join_room", { room: room });
        });

        socket.on("role_assigned", function (payload) {
            myColor = payload.color;
            myHand = payload.hand || [];
            const snap = payload.snapshot || null;

            if (myColor === "w") {
                $("#my-name").text("You (White)");
                $("#opp-name").text("Opponent (Black)");
                $("#my-avatar").text("P1");
                $("#opp-avatar").text("P2");
                board.orientation("white");
            } else if (myColor === "b") {
                $("#my-name").text("You (Black)");
                $("#opp-name").text("Opponent (White)");
                $("#my-avatar").text("P1");
                $("#opp-avatar").text("P2");
                board.orientation("black");
            } else {
                $("#my-name").text("Spectator");
                $("#my-sub").text("You are watching the game.");
            }

            renderHand(myHand);
            syncBoard(snap ? snap.fen : game.fen(), false);
            applyRoomState(snap || {});
            if (myColor === "w" || myColor === "b") {
                showPopup(`You are ${myColor === "w" ? "White" : "Black"}.`);
            }
        });

        socket.on("room_state", function (state) {
            if (!state) return;
            applyRoomState(state);
        });

        socket.on("game_ready", function (state) {
            gameStarted = true;
            $("#lobby-box").slideUp(180);
            $("#mini-state").text("The match has begun.");
            sfxStart.play();
            applyRoomState(state);
        });

        socket.on("standard_move", function (payload) {
            if (!payload || !payload.fen) return;
            game.load(payload.fen);
            board.position(payload.fen);
            if (fenHistory[fenHistory.length - 1] !== payload.fen) fenHistory.push(payload.fen);
            appendMove({ color: payload.color, san: payload.san, from: payload.from, to: payload.to });
            if (payload.san && payload.san.indexOf("x") !== -1) sfxCapture.play();
            else sfxMove.play();
            updateCapturedPieces();
            setTurnUI();
        });

        socket.on("spell_effect", function (payload) {
            if (!payload) return;

            clearSpellMode();

            if (payload.consume_turn) {
                if (payload.fen) {
                    game.load(payload.fen);
                    board.position(payload.fen);
                    if (fenHistory[fenHistory.length - 1] !== payload.fen) fenHistory.push(payload.fen);
                    updateCapturedPieces();
                }
                appendSpellLog(payload.name.toUpperCase());
                sfxSpell.play();
                setTurnUI();
            } else {
                appendSpellLog(payload.name.toUpperCase());
                showPopup("Expelliarmus! You get another move.");
                sfxSpell.play();
            }
        });

        socket.on("action_denied", function (payload) {
            clearSpellMode();
            if (payload && payload.snapshot && payload.snapshot.fen) {
                game.load(payload.snapshot.fen);
                board.position(payload.snapshot.fen);
                if (fenHistory[fenHistory.length - 1] !== payload.snapshot.fen) fenHistory.push(payload.snapshot.fen);
                updateCapturedPieces();
            }
            setTurnUI();
            showPopup(payload && payload.reason ? payload.reason : "Action denied.");
        });

        socket.on("disconnect", function () {
            setStatus("Disconnected");
            $("#my-sub").text("Connection lost.");
            $("#opp-sub").text("Connection lost.");
        });

        setTurnUI();
        updateCapturedPieces();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"> SERVER ONLINE. PORT: {port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
