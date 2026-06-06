import os
import random
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'wizard_chess_secret_v3')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

SPELLS = [
    {'id': 'avada', 'name': 'Avada Kedavra', 'rarity': 'Legendary', 'icon': '⚡', 'action': 'click', 'desc': 'Click an enemy piece to destroy it.'},
    {'id': 'time', 'name': 'Time-Turner', 'rarity': 'Legendary', 'icon': '⏳', 'action': 'instant', 'desc': 'Rewind the board to the previous state.'},
    {'id': 'imperio', 'name': 'Imperio', 'rarity': 'Rare', 'icon': '👁️', 'action': 'drag', 'desc': 'Drag an enemy piece to make a legal move for them.'},
    {'id': 'sectum', 'name': 'Sectumsempra', 'rarity': 'Rare', 'icon': '🩸', 'action': 'click', 'desc': 'Click an enemy piece to demote it to a Pawn.'},
    {'id': 'fiendfyre', 'name': 'Fiendfyre', 'rarity': 'Rare', 'icon': '🔥', 'action': 'click', 'desc': 'Click a square to destroy it and the surrounding 8 squares.'},
    {'id': 'accio', 'name': 'Accio', 'rarity': 'Common', 'icon': '🧲', 'action': 'drag', 'desc': 'Drag one of your pieces up to 2 squares in any direction.'},
    {'id': 'leviosa', 'name': 'Wingardium Leviosa', 'rarity': 'Common', 'icon': '🪶', 'action': 'drag', 'desc': 'Drag one of your pieces to any adjacent empty square.'},
    {'id': 'alohomora', 'name': 'Alohomora', 'rarity': 'Common', 'icon': '🗝️', 'action': 'drag', 'desc': 'Drag one of your pieces to any empty square on your half.'},
    {'id': 'expelliarmus', 'name': 'Expelliarmus', 'rarity': 'Common', 'icon': '🪄', 'action': 'instant', 'desc': 'Keep your turn and move again.'},
    {'id': 'protego', 'name': 'Protego', 'rarity': 'Common', 'icon': '🛡️', 'action': 'click', 'desc': 'Click one of your Pawns to promote it to a Knight.'},
]

ROOMS = {}
SID_TO_ROOM = {}


def opp(color: str) -> str:
    return 'b' if color == 'w' else 'w'


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
            'players': {'w': None, 'b': None},
            'hands': {'w': None, 'b': None},
            'used': {'w': set(), 'b': set()},
            'sid_to_color': {},
        }
    return ROOMS[room_id]


def snapshot(room_id: str):
    room = ROOMS[room_id]
    return {
        'room': room_id,
        'fen': room['fen'],
        'turn': room['turn'],
        'white_connected': room['players']['w'] is not None,
        'black_connected': room['players']['b'] is not None,
        'started': room['players']['w'] is not None and room['players']['b'] is not None,
    }


def color_for_sid(room, sid):
    return room['sid_to_color'].get(sid)


@app.route('/')
def index():
    return render_template_string(HTML_PAYLOAD)


@socketio.on('join_room')
def handle_join(data):
    room_id = data['room'] if isinstance(data, dict) else str(data)
    room = get_room(room_id)

    if room['players']['w'] is None:
        color = 'w'
    elif room['players']['b'] is None:
        color = 'b'
    else:
        color = 's'

    join_room(room_id)
    SID_TO_ROOM[request.sid] = room_id

    if color in ('w', 'b'):
        room['players'][color] = request.sid
        room['sid_to_color'][request.sid] = color
        if room['hands'][color] is None:
            room['hands'][color] = fresh_hand()

    emit('role_assigned', {
        'color': color,
        'hand': room['hands'].get(color, []) if color in ('w', 'b') else [],
        'snapshot': snapshot(room_id),
    }, to=request.sid)

    emit('room_state', snapshot(room_id), room=room_id)
    if room['players']['w'] is not None and room['players']['b'] is not None:
        emit('game_ready', snapshot(room_id), room=room_id)


@socketio.on('standard_move')
def handle_standard_move(data):
    room_id = SID_TO_ROOM.get(request.sid)
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    color = color_for_sid(room, request.sid)
    if color not in ('w', 'b'):
        return

    if room['players']['w'] is None or room['players']['b'] is None:
        emit('action_denied', {'reason': 'Waiting for both players.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    if room['turn'] != color:
        emit('action_denied', {'reason': 'It is not your turn.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    base_fen = data.get('base_fen')
    new_fen = data.get('fen')
    if base_fen != room['fen']:
        emit('action_denied', {'reason': 'Board out of sync. Resyncing.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    if not new_fen:
        emit('action_denied', {'reason': 'Missing move data.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    room['fen'] = new_fen
    room['turn'] = fen_side_to_move(new_fen)
    room['history'].append(new_fen)

    emit('standard_move', {
        'from': data.get('from'),
        'to': data.get('to'),
        'san': data.get('san'),
        'color': color,
        'fen': room['fen'],
        'turn': room['turn'],
    }, room=room_id, include_self=False)


@socketio.on('spell_effect')
def handle_spell_effect(data):
    room_id = SID_TO_ROOM.get(request.sid)
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    color = color_for_sid(room, request.sid)
    if color not in ('w', 'b'):
        return

    if room['players']['w'] is None or room['players']['b'] is None:
        emit('action_denied', {'reason': 'Waiting for both players.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    if room['turn'] != color:
        emit('action_denied', {'reason': 'It is not your turn.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    spell_id = data.get('spell_id')
    if spell_id in room['used'][color]:
        emit('action_denied', {'reason': 'That spell has already been used.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    base_fen = data.get('base_fen')
    if base_fen != room['fen']:
        emit('action_denied', {'reason': 'Board out of sync. Resyncing.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    consume_turn = bool(data.get('consume_turn', True))
    new_fen = data.get('fen')

    if spell_id == 'time':
        if len(room['history']) < 2:
            emit('action_denied', {'reason': 'Not enough history to rewind.', 'snapshot': snapshot(room_id)}, to=request.sid)
            return
        new_fen = room['history'][-2]
        consume_turn = True

    if spell_id == 'expelliarmus':
        consume_turn = False
        if not new_fen:
            new_fen = room['fen']

    if not new_fen:
        emit('action_denied', {'reason': 'Missing spell data.', 'snapshot': snapshot(room_id)}, to=request.sid)
        return

    room['used'][color].add(spell_id)
    room['fen'] = new_fen
    if consume_turn:
        room['turn'] = fen_side_to_move(new_fen)
    room['history'].append(new_fen)

    emit('spell_effect', {
        'spell_id': spell_id,
        'name': data.get('name', spell_id),
        'fen': room['fen'],
        'consume_turn': consume_turn,
        'color': color,
        'turn': room['turn'],
        'log': data.get('log', ''),
    }, room=room_id, include_self=False)


@socketio.on('disconnect')
def handle_disconnect():
    room_id = SID_TO_ROOM.pop(request.sid, None)
    if not room_id or room_id not in ROOMS:
        return

    room = ROOMS[room_id]
    color = room['sid_to_color'].pop(request.sid, None)
    if color in ('w', 'b') and room['players'].get(color) == request.sid:
        room['players'][color] = None

    try:
        leave_room(room_id)
    except Exception:
        pass

    emit('room_state', snapshot(room_id), room=room_id)

    if room['players']['w'] is None and room['players']['b'] is None:
        ROOMS.pop(room_id, None)


HTML_PAYLOAD = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>Wizard's Chess</title>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>

    <style>
        :root{
            --bg:#1a1917;
            --panel:#262421;
            --border:#3f3c39;
            --text:#f5f5f5;
            --muted:#a2a19d;
            --accent:#81b64c;
            --accent2:#9ed65b;
            --white:#eeeed2;
            --black:#769656;
            --gold:#f1b24a;
            --purple:#a855f7;
            --silver:#b7b7b3;
            --glow:rgba(168,85,247,.35);
        }
        *{box-sizing:border-box}
        html,body{margin:0;padding:0;min-height:100%}
        body{
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
            background:linear-gradient(180deg,#141312 0%, #1e1d1b 100%);
            color:var(--text);
        }
        .topbar{
            position:sticky; top:0; z-index:50; height:64px; background:#111010;
            border-bottom:1px solid #000; display:flex; align-items:center; justify-content:space-between;
            padding:0 16px; box-shadow:0 6px 22px rgba(0,0,0,.25);
        }
        .brand{display:flex; align-items:center; gap:10px; font-weight:900; font-size:1.08rem;}
        .brand-badge{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;background:linear-gradient(135deg,var(--accent),#5f8f33);color:#111;}
        .top-actions{display:flex;align-items:center;gap:10px;}
        .pill{padding:8px 12px;border:1px solid var(--border);border-radius:999px;background:#201f1d;color:var(--muted);font-size:.92rem;}
        .info-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:#23211f;color:#fff;cursor:pointer;font-weight:900;}
        .page{width:min(1400px,100%);margin:0 auto;padding:18px;}
        .layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:18px;align-items:start;}
        .board-column{min-width:0;}
        .player-strip{background:var(--panel);border:1px solid var(--border);padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:12px;}
        .player-strip.top{border-radius:18px 18px 0 0;border-bottom:none;}
        .player-strip.bottom{border-radius:0 0 18px 18px;border-top:none;}
        .player-left{display:flex;align-items:center;gap:10px;min-width:0;}
        .avatar{width:38px;height:38px;border-radius:10px;flex:0 0 auto;display:grid;place-items:center;font-weight:900;background:#48453f;color:#fff;}
        .avatar.green{background:var(--accent);color:#111;}
        .player-text{min-width:0;}
        .player-name{font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .player-sub{margin-top:2px;color:var(--muted);font-size:.82rem;}
        .clock{min-width:96px;text-align:center;padding:9px 12px;border-radius:10px;border:1px solid #41403c;background:#171614;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:900;letter-spacing:.3px;}
        .clock.active{background:#f6f6f6;color:#111;border-color:#f6f6f6;}
        .captured{background:var(--panel);border-left:1px solid var(--border);border-right:1px solid var(--border);min-height:34px;padding:8px 14px 10px;display:flex;align-items:center;flex-wrap:wrap;gap:6px;}
        .captured-piece{width:22px;height:22px;background-size:contain;background-repeat:no-repeat;background-position:center;border-radius:4px;}
        .material-adv{margin-left:8px;color:var(--muted);font-weight:700;font-size:.84rem;}
        .board-shell{background:#111;border:1px solid var(--border);border-top:none;border-bottom:none;padding:12px;box-shadow:0 16px 34px rgba(0,0,0,.28);}
        .board-shell-inner{position:relative;border-radius:14px;overflow:hidden;box-shadow:0 0 0 1px rgba(255,255,255,.03),0 16px 40px rgba(0,0,0,.35);}
        .board-shell-inner.magic-active{box-shadow:0 0 0 1px rgba(168,85,247,.55),0 0 30px var(--glow),0 16px 40px rgba(0,0,0,.35);cursor:crosshair;}
        #board{width:100%;max-width:100%;}
        .board-overlay{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.5);backdrop-filter:blur(2px);z-index:5;text-align:center;padding:18px;}
        .board-overlay .overlay-box{background:rgba(20,20,20,.92);border:1px solid var(--border);border-radius:16px;padding:18px 16px;max-width:90%;}
        .overlay-title{font-weight:900;font-size:1.02rem;margin-bottom:6px;}
        .overlay-sub{color:var(--muted);font-size:.92rem;line-height:1.45;}
        .spell-banner{display:none;margin-top:12px;padding:12px 14px;border-radius:12px;background:linear-gradient(135deg,#7c3aed,#a855f7);border:1px solid rgba(255,255,255,.08);font-weight:900;box-shadow:0 10px 24px rgba(0,0,0,.22);}
        .hand-panel{background:var(--panel);border:1px solid var(--border);border-radius:18px;margin-top:12px;padding:14px;box-shadow:0 12px 24px rgba(0,0,0,.2);}
        .hand-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;}
        .hand-title{font-size:.8rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);font-weight:900;}
        .hand-note{color:var(--muted);font-size:.82rem;text-align:right;}
        .spells-row{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;}
        .spell-card{min-width:96px;width:96px;height:128px;padding:10px 8px;border-radius:14px;border:1px solid var(--border);background:linear-gradient(180deg,#312f2b 0%, #24221f 100%);display:flex;flex-direction:column;align-items:center;justify-content:flex-start;text-align:center;cursor:pointer;transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease,opacity .15s ease;}
        .spell-card:hover{transform:translateY(-3px);border-color:#64615b;box-shadow:0 8px 18px rgba(0,0,0,.25);}
        .spell-card.used{opacity:.18;pointer-events:none;filter:grayscale(100%);}
        .spell-card.Legendary{border-bottom:4px solid var(--gold);}
        .spell-card.Rare{border-bottom:4px solid var(--purple);}
        .spell-card.Common{border-bottom:4px solid var(--silver);}
        .spell-icon{font-size:1.8rem;margin-top:8px;margin-bottom:10px;text-shadow:0 2px 4px rgba(0,0,0,.35);}
        .spell-name{font-size:.74rem;font-weight:900;line-height:1.1;}
        .spell-desc{margin-top:6px;font-size:.68rem;color:var(--muted);line-height:1.2;}
        .sidebar{display:flex;flex-direction:column;gap:12px;min-width:0;}
        .card{background:var(--panel);border:1px solid var(--border);border-radius:18px;overflow:hidden;box-shadow:0 12px 24px rgba(0,0,0,.18);}
        .card-head{padding:14px 16px;background:#211f1c;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:10px;}
        .card-title{font-size:.9rem;font-weight:900;letter-spacing:.03em;}
        .card-body{padding:0;max-height:560px;overflow:auto;}
        .move-history{display:grid;grid-template-columns:42px 1fr 1fr;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.94rem;}
        .move-row{display:contents;}
        .move-row > div{padding:10px 12px;border-bottom:1px solid var(--border);}
        .move-num{background:#201e1b;color:var(--muted);text-align:right;}
        .move-ply{font-weight:700;}
        .spell-ply{grid-column:span 2;color:#d9b8ff;background:#241b2d;font-weight:900;}
        .lobby{padding:16px;display:flex;flex-direction:column;gap:10px;}
        .lobby input{width:100%;border-radius:10px;border:1px solid var(--border);background:#141312;color:#fff;padding:12px 12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9rem;}
        .btn{width:100%;border:none;border-radius:10px;padding:12px 14px;background:var(--accent);color:#101010;font-weight:900;cursor:pointer;text-transform:uppercase;letter-spacing:.02em;}
        .btn:hover{background:var(--accent2);}
        .mini-state{padding:16px;color:var(--muted);line-height:1.45;font-size:.95rem;}
        .notification{position:fixed;left:50%;top:88px;transform:translateX(-50%);display:none;z-index:200;max-width:min(92vw,700px);padding:12px 16px;border-radius:12px;background:rgba(15,15,15,.92);color:#fff;border:1px solid rgba(168,85,247,.65);box-shadow:0 0 30px var(--glow);font-weight:900;text-align:center;}
        .modal-overlay{position:fixed;inset:0;display:none;justify-content:center;align-items:center;background:rgba(0,0,0,.82);z-index:300;padding:20px;}
        .modal{width:min(820px,100%);max-height:88vh;overflow:auto;border-radius:18px;background:#1f1d1b;border:1px solid var(--border);box-shadow:0 24px 60px rgba(0,0,0,.55);padding:22px;}
        .modal h2{margin:0 0 10px 0;}
        .modal p{color:#d8d8d8;line-height:1.55;}
        .grimoire{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:14px;}
        .spell-item{background:#24221f;border:1px solid var(--border);border-radius:14px;padding:12px;}
        .spell-item h4{margin:0 0 6px 0;}
        .spell-item p{margin:0;font-size:.92rem;color:#cfcfcf;}
        .tap-hint{display:none;color:var(--muted);font-size:.82rem;margin-top:8px;}
        @media (max-width:1080px){.layout{grid-template-columns:1fr}.card-body{max-height:none}}
        @media (pointer:coarse){.tap-hint{display:block}}
    </style>
</head>
<body>
    <div class="topbar">
        <div class="brand"><div class="brand-badge">♞</div><div>Wizard's Chess</div></div>
        <div class="top-actions"><div class="pill" id="status-pill">Connecting…</div><button class="info-btn" id="help-btn">i</button></div>
    </div>

    <div class="notification" id="notification"></div>

    <div class="page">
        <div class="layout">
            <div class="board-column">
                <div class="player-strip top">
                    <div class="player-left">
                        <div class="avatar" id="opp-avatar">P2</div>
                        <div class="player-text"><div class="player-name" id="opp-name">Opponent</div><div class="player-sub" id="opp-sub">Waiting for a challenger…</div></div>
                    </div>
                    <div class="clock" id="clock-opp">10:00</div>
                </div>

                <div class="captured" id="opp-captured"></div>

                <div class="board-shell">
                    <div class="board-shell-inner" id="board-shell">
                        <div id="board"></div>
                        <div class="board-overlay" id="board-overlay"><div class="overlay-box"><div class="overlay-title">Waiting for opponent</div><div class="overlay-sub">Share the room link. The board becomes live when both players join.</div></div></div>
                    </div>
                    <div class="spell-banner" id="spell-banner"></div>
                    <div class="tap-hint">On phones and iPads, tap a piece once, then tap the target square.</div>
                </div>

                <div class="captured" id="my-captured"></div>

                <div class="player-strip bottom">
                    <div class="player-left">
                        <div class="avatar green" id="my-avatar">P1</div>
                        <div class="player-text"><div class="player-name" id="my-name">You</div><div class="player-sub" id="my-sub">Waiting for game start.</div></div>
                    </div>
                    <div class="clock active" id="clock-my">10:00</div>
                </div>

                <div class="hand-panel">
                    <div class="hand-head"><div class="hand-title">Your Hand</div><div class="hand-note">6 spells: 1 Legendary, 2 Rare, 3 Common</div></div>
                    <div class="spells-row" id="spells-view"></div>
                </div>
            </div>

            <div class="sidebar">
                <div class="card">
                    <div class="card-head"><div class="card-title">Match Telemetry</div><div style="color:var(--muted);font-size:.82rem" id="room-tag">Room</div></div>
                    <div class="card-body"><div class="move-history" id="move-history"></div></div>
                </div>

                <div class="card">
                    <div class="card-head"><div class="card-title">Invite</div><div style="color:var(--muted);font-size:.82rem" id="state-tag">Waiting</div></div>
                    <div class="lobby" id="lobby-box"><input type="text" id="shareLink" readonly /><button class="btn" id="copy-btn">Copy Link</button></div>
                    <div class="mini-state" id="mini-state">Share the link above to start a game. When the second player joins, the board unlocks and both hands become live.</div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="rules-modal">
        <div class="modal">
            <h2>How to Play Wizard's Chess</h2>
            <p>Each player gets exactly 6 spells: 1 Legendary, 2 Rare, and 3 Common. The server enforces the turn order, and spells cannot be used out of turn.</p>
            <p>Expelliarmus does not end your turn. Time-Turner rewinds to the previous board state. Kings are never directly destroyed by spells.</p>
            <div class="grimoire">
                <div class="spell-item"><h4 style="color:var(--gold)">Avada Kedavra</h4><p>Click an enemy piece to destroy it.</p></div>
                <div class="spell-item"><h4 style="color:var(--gold)">Time-Turner</h4><p>Rewind to the previous board state.</p></div>
                <div class="spell-item"><h4 style="color:var(--purple)">Imperio</h4><p>Force a legal move from an enemy piece.</p></div>
                <div class="spell-item"><h4 style="color:var(--purple)">Sectumsempra</h4><p>Demote an enemy piece to a Pawn.</p></div>
                <div class="spell-item"><h4 style="color:var(--purple)">Fiendfyre</h4><p>Destroy a square and adjacent squares.</p></div>
                <div class="spell-item"><h4 style="color:var(--silver)">Accio</h4><p>Move your piece up to 2 squares in any direction.</p></div>
                <div class="spell-item"><h4 style="color:var(--silver)">Wingardium Leviosa</h4><p>Move your piece to any adjacent empty square.</p></div>
                <div class="spell-item"><h4 style="color:var(--silver)">Alohomora</h4><p>Move your piece to any empty square on your half.</p></div>
                <div class="spell-item"><h4 style="color:var(--silver)">Expelliarmus</h4><p>You move again immediately.</p></div>
                <div class="spell-item"><h4 style="color:var(--silver)">Protego</h4><p>Promote one of your Pawns to a Knight.</p></div>
            </div>
            <div style="margin-top:18px"><button class="btn" id="close-help" style="max-width:220px;">Close Manual</button></div>
        </div>
    </div>

    <script>
        const socket = io();
        const room = (() => {
            const params = new URLSearchParams(location.search);
            let r = params.get('room');
            if (!r) {
                r = Math.random().toString(36).slice(2, 9);
                history.replaceState({}, '', `${location.pathname}?room=${r}`);
            }
            return r;
        })();

        document.getElementById('shareLink').value = location.href;
        document.getElementById('room-tag').textContent = `Room ${room}`;

        const sfxMove = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3');
        const sfxCapture = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3');
        const sfxStart = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/game-start.mp3');
        const sfxSpell = new Audio('https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3');

        const game = new Chess();
        const touchMode = window.matchMedia('(pointer: coarse)').matches || ('ontouchstart' in window);
        let board = null;
        let myColor = null;
        let myHand = [];
        let activeSpell = null;
        let selectedSquare = null;
        let fenHistory = [game.fen()];
        let moveNum = 1;
        let gameReady = false;
        let suppressNextClick = false;

        function showPopup(msg) {
            const el = $('#notification');
            el.text(msg).stop(true, true).fadeIn(160);
            setTimeout(() => el.fadeOut(260), 2200);
        }

        function setStatus(text) {
            $('#status-pill').text(text);
            $('#state-tag').text(text);
        }

        function clearSpellMode() {
            activeSpell = null;
            selectedSquare = null;
            $('#board-shell').removeClass('magic-active');
            $('#spell-banner').hide().text('');
        }

        function isMyTurn() {
            return myColor && myColor !== 's' && gameReady && game.turn() === myColor;
        }

        function updateTurnUI() {
            if (!myColor) return;
            const myTurn = game.turn() === myColor;
            $('#clock-my').toggleClass('active', myTurn);
            $('#clock-opp').toggleClass('active', !myTurn);

            if (game.game_over()) {
                setStatus('Game over');
                $('#my-sub').text('Game finished.');
                $('#opp-sub').text('Game finished.');
                return;
            }

            if (!gameReady) {
                setStatus('Waiting for opponent');
                $('#my-sub').text('Waiting for the second player.');
                $('#opp-sub').text('Waiting for the second player.');
                $('#board-overlay').css('display', 'flex');
                return;
            }

            $('#board-overlay').hide();
            setStatus(myTurn ? 'Your turn' : 'Opponent\'s turn');
            $('#my-sub').text(myTurn ? 'You can move now.' : 'Waiting for the opponent.');
            $('#opp-sub').text(myTurn ? 'Waiting for the opponent.' : 'Thinking…');
        }

        function appendMove(move) {
            const san = move.san || `${move.from}-${move.to}`;
            if (move.color === 'w') {
                $('#move-history').append(`<div class="move-row"><div class="move-num">${moveNum}.</div><div class="move-ply">${san}</div><div class="move-ply"></div></div>`);
            } else {
                const rows = $('#move-history .move-row');
                const last = rows.last();
                if (last.length && last.find('.move-ply').eq(2).text().trim() === '') {
                    last.find('.move-ply').eq(2).text(san);
                } else {
                    $('#move-history').append(`<div class="move-row"><div class="move-num">${moveNum}.</div><div class="move-ply"></div><div class="move-ply">${san}</div></div>`);
                }
                moveNum += 1;
            }
        }

        function appendSpell(text) {
            $('#move-history').append(`<div class="move-row"><div></div><div class="move-ply spell-ply">${text}</div></div>`);
        }

        function updateCapturedPieces() {
            const boardFen = game.fen().split(' ')[0];
            const counts = { w: { p:0, n:0, b:0, r:0, q:0 }, b: { p:0, n:0, b:0, r:0, q:0 } };
            for (const ch of boardFen) {
                if (ch >= 'a' && ch <= 'z' && counts.b[ch] !== undefined) counts.b[ch]++;
                if (ch >= 'A' && ch <= 'Z') {
                    const p = ch.toLowerCase();
                    if (counts.w[p] !== undefined) counts.w[p]++;
                }
            }
            const base = { p:8, n:2, b:2, r:2, q:1 };
            const values = { p:1, n:3, b:3, r:5, q:9 };
            let capW = '', capB = '', wScore = 0, bScore = 0;
            ['q','r','b','n','p'].forEach(p => {
                const wMissing = base[p] - counts.w[p];
                const bMissing = base[p] - counts.b[p];
                for (let i = 0; i < bMissing; i++) { capW += `<div class="captured-piece" style="background-image:url('https://chessboardjs.com/img/chesspieces/wikipedia/b${p.toUpperCase()}.png')"></div>`; wScore += values[p]; }
                for (let i = 0; i < wMissing; i++) { capB += `<div class="captured-piece" style="background-image:url('https://chessboardjs.com/img/chesspieces/wikipedia/w${p.toUpperCase()}.png')"></div>`; bScore += values[p]; }
            });
            const wAdv = wScore - bScore;
            const bAdv = bScore - wScore;
            if (wAdv > 0) capW += `<span class="material-adv">+${wAdv}</span>`;
            if (bAdv > 0) capB += `<span class="material-adv">+${bAdv}</span>`;
            if (myColor === 'w') { $('#my-captured').html(capW); $('#opp-captured').html(capB); }
            else if (myColor === 'b') { $('#my-captured').html(capB); $('#opp-captured').html(capW); }
        }

        function renderHand(hand) {
            $('#spells-view').empty();
            hand.forEach(spell => {
                const card = $(`<div class="spell-card ${spell.rarity}" id="card-${spell.id}" title="${spell.desc}"><div class="spell-icon">${spell.icon}</div><div class="spell-name">${spell.name}</div><div class="spell-desc">${spell.desc}</div></div>`);
                card.on('click', function() {
                    if (!myColor || myColor === 's') { showPopup('You are spectating.'); return; }
                    if (!gameReady) { showPopup('Wait for the second player.'); return; }
                    if (game.turn() !== myColor) { showPopup('You can only cast spells on your turn.'); return; }
                    if ($(this).hasClass('used')) return;

                    const baseFen = game.fen();

                    if (spell.id === 'time') {
                        if (fenHistory.length < 2) { showPopup('Not enough history to rewind yet.'); return; }
                        const rewindFen = fenHistory[fenHistory.length - 2];
                        game.load(rewindFen);
                        board.position(rewindFen);
                        fenHistory.push(rewindFen);
                        $(this).addClass('used');
                        clearSpellMode();
                        sfxSpell.play();
                        appendSpell('TIME-TURNER');
                        updateCapturedPieces();
                        updateTurnUI();
                        socket.emit('spell_effect', { room, base_fen: baseFen, spell_id: spell.id, name: spell.name, fen: rewindFen, consume_turn: true, log: 'TIME-TURNER' });
                        return;
                    }

                    if (spell.id === 'expelliarmus') {
                        $(this).addClass('used');
                        clearSpellMode();
                        sfxSpell.play();
                        appendSpell('EXPELLIARMUS');
                        showPopup('Expelliarmus! You move again.');
                        updateTurnUI();
                        socket.emit('spell_effect', { room, base_fen: baseFen, spell_id: spell.id, name: spell.name, fen: game.fen(), consume_turn: false, log: 'EXPELLIARMUS' });
                        return;
                    }

                    activeSpell = spell;
                    $('#board-shell').addClass('magic-active');
                    $('#spell-banner').text(`🪄 ${spell.name.toUpperCase()}: ${spell.desc}`).fadeIn(120);
                    showPopup(`${spell.name} armed.`);
                });
                $('#spells-view').append(card);
            });
        }

        function finishTargetedSpell(spell, baseFen, logText) {
            $(`#card-${spell.id}`).addClass('used');
            clearSpellMode();
            sfxSpell.play();
            appendSpell(logText || spell.name.toUpperCase());
            updateCapturedPieces();
            updateTurnUI();
            socket.emit('spell_effect', { room, base_fen: baseFen, spell_id: spell.id, name: spell.name, fen: game.fen(), consume_turn: true, log: logText || spell.name.toUpperCase() });
        }

        function isOnYourHalf(square) {
            const rank = parseInt(square[1], 10);
            return myColor === 'w' ? rank <= 4 : rank >= 5;
        }

        function tryTapMove(square) {
            if (!myColor || myColor === 's' || !gameReady) return;
            if (activeSpell) return;
            if (!isMyTurn()) return;

            const piece = game.get(square);
            if (!selectedSquare) {
                if (piece && piece.color === myColor) {
                    selectedSquare = square;
                    $('#status-pill').text(`Selected ${square.toUpperCase()}`);
                }
                return;
            }

            if (selectedSquare === square) {
                selectedSquare = null;
                updateTurnUI();
                return;
            }

            const baseFen = game.fen();
            const move = game.move({ from: selectedSquare, to: square, promotion: 'q' });
            if (!move) {
                if (piece && piece.color === myColor) {
                    selectedSquare = square;
                    $('#status-pill').text(`Selected ${square.toUpperCase()}`);
                } else {
                    selectedSquare = null;
                    showPopup('Illegal move.');
                    updateTurnUI();
                }
                return;
            }

            selectedSquare = null;
            board.position(game.fen());
            fenHistory.push(game.fen());
            if (move.captured) sfxCapture.play(); else sfxMove.play();
            appendMove(move);
            updateCapturedPieces();
            updateTurnUI();
            socket.emit('standard_move', { room, base_fen: baseFen, from: move.from, to: move.to, san: move.san, color: move.color, fen: game.fen() });
        }

        function onDragStart(source, piece) {
            if (touchMode) return false;
            if (game.game_over()) return false;
            if (!myColor || myColor === 's' || !gameReady) return false;

            if (activeSpell) {
                if (activeSpell.action !== 'drag') return false;
                if (activeSpell.id === 'imperio') return piece.charAt(0) !== myColor;
                return piece.charAt(0) === myColor;
            }

            if (game.turn() !== myColor) return false;
            return piece.charAt(0) === myColor;
        }

        function onDrop(source, target) {
            if (touchMode) return 'snapback';

            if (activeSpell && activeSpell.action === 'drag') {
                const baseFen = game.fen();
                const movingPiece = game.get(source);
                const targetPiece = game.get(target);
                if (!movingPiece) return 'snapback';
                if (targetPiece && targetPiece.type === 'k') return 'snapback';

                const fileDist = Math.abs(source.charCodeAt(0) - target.charCodeAt(0));
                const rankDist = Math.abs(parseInt(source[1], 10) - parseInt(target[1], 10));

                if (activeSpell.id === 'imperio') {
                    const originalFen = game.fen();
                    const parts = originalFen.split(' ');
                    parts[1] = opp(myColor);
                    game.load(parts.join(' '));
                    const move = game.move({ from: source, to: target, promotion: 'q' });
                    if (!move) { game.load(originalFen); return 'snapback'; }
                    board.position(game.fen());
                    fenHistory.push(game.fen());
                    finishTargetedSpell(activeSpell, baseFen, `IMPERIO: ${move.san}`);
                    return;
                }

                if (activeSpell.id === 'accio') {
                    if (fileDist <= 2 && rankDist <= 2) {
                        game.remove(source);
                        game.put(movingPiece, target);
                        game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, baseFen, 'ACCIO');
                        return;
                    }
                    return 'snapback';
                }

                if (activeSpell.id === 'leviosa') {
                    if (fileDist <= 1 && rankDist <= 1 && !targetPiece) {
                        game.remove(source);
                        game.put(movingPiece, target);
                        game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, baseFen, 'WINGARDIUM LEVIOSA');
                        return;
                    }
                    return 'snapback';
                }

                if (activeSpell.id === 'alohomora') {
                    if (!targetPiece && isOnYourHalf(target)) {
                        game.remove(source);
                        game.put(movingPiece, target);
                        game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, baseFen, 'ALOHOMORA');
                        return;
                    }
                    return 'snapback';
                }

                return 'snapback';
            }

            if (!myColor || myColor === 's' || !gameReady) return 'snapback';
            if (game.turn() !== myColor) return 'snapback';

            const baseFen = game.fen();
            const move = game.move({ from: source, to: target, promotion: 'q' });
            if (move === null) return 'snapback';

            board.position(game.fen());
            fenHistory.push(game.fen());
            if (move.captured) sfxCapture.play(); else sfxMove.play();
            appendMove(move);
            updateCapturedPieces();
            updateTurnUI();
            socket.emit('standard_move', { room, base_fen: baseFen, from: source, to: target, san: move.san, color: move.color, fen: game.fen() });
        }

        function onSnapEnd() { board.position(game.fen()); }

        function onSquareTap(square) {
            if (suppressNextClick) { suppressNextClick = false; return; }
            if (activeSpell && activeSpell.action === 'click') {
                const p = game.get(square);
                const baseFen = game.fen();

                if (activeSpell.id === 'avada') {
                    if (p && p.color !== myColor && p.type !== 'k') {
                        game.remove(square);
                        game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, baseFen, 'AVADA KEDAVRA');
                    } else {
                        showPopup('Click a non-King enemy piece.');
                    }
                    return;
                }

                if (activeSpell.id === 'sectum') {
                    if (p && p.color !== myColor && p.type !== 'k') {
                        game.remove(square);
                        game.put({ type: 'p', color: p.color }, square);
                        game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, baseFen, 'SECTUMSEMPRA');
                    } else {
                        showPopup('Click an enemy piece.');
                    }
                    return;
                }

                if (activeSpell.id === 'fiendfyre') {
                    const file = square.charCodeAt(0);
                    const rank = parseInt(square[1], 10);
                    for (let f = file - 1; f <= file + 1; f++) {
                        for (let r = rank - 1; r <= rank + 1; r++) {
                            const sq = String.fromCharCode(f) + String(r);
                            const t = game.get(sq);
                            if (t && t.type !== 'k') game.remove(sq);
                        }
                    }
                    game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                    board.position(game.fen());
                    fenHistory.push(game.fen());
                    finishTargetedSpell(activeSpell, baseFen, 'FIENDFYRE');
                    return;
                }

                if (activeSpell.id === 'protego') {
                    if (p && p.color === myColor && p.type === 'p') {
                        game.remove(square);
                        game.put({ type: 'n', color: myColor }, square);
                        game.load(game.fen().split(' ').slice(0,4).join(' ') + ' ' + opp(myColor) + ' - 0 1');
                        board.position(game.fen());
                        fenHistory.push(game.fen());
                        finishTargetedSpell(activeSpell, baseFen, 'PROTEGO');
                    } else {
                        showPopup('Click one of your Pawns.');
                    }
                    return;
                }
            }

            if (touchMode) tryTapMove(square);
        }

        function resizeBoard() { if (board && board.resize) board.resize(); }

        board = Chessboard('board', {
            draggable: !touchMode,
            position: 'start',
            orientation: 'white',
            pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
            onDragStart: onDragStart,
            onDrop: onDrop,
            onSnapEnd: onSnapEnd,
        });

        $(window).on('resize orientationchange', function() { resizeBoard(); });
        setTimeout(resizeBoard, 120);
        setTimeout(resizeBoard, 450);

        $('#board').on('click', '.square-55d63', function() {
            const square = $(this).attr('data-square');
            onSquareTap(square);
        });

        function applySnapshot(state) {
            if (!state) return;
            $('#room-tag').text(`Room ${state.room}`);
            gameReady = !!state.started;
            if (state.white_connected && state.black_connected) {
                $('#lobby-box').slideUp(180);
                $('#mini-state').text('Both players connected. The match is live.');
                $('#board-overlay').hide();
            } else {
                $('#board-overlay').css('display', 'flex');
                $('#mini-state').text('Share the room link to start a game.');
            }
            updateTurnUI();
        }

        socket.on('connect', function() {
            setStatus('Joining room…');
            socket.emit('join_room', { room });
        });

        socket.on('role_assigned', function(payload) {
            myColor = payload.color;
            myHand = payload.hand || [];
            const snap = payload.snapshot;

            if (myColor === 'w') {
                $('#my-name').text('You (White)');
                $('#opp-name').text('Opponent (Black)');
                board.orientation('white');
            } else if (myColor === 'b') {
                $('#my-name').text('You (Black)');
                $('#opp-name').text('Opponent (White)');
                board.orientation('black');
            } else {
                $('#my-name').text('Spectator');
                $('#my-sub').text('Watching the match.');
                $('#opp-name').text('Player 2');
            }

            renderHand(myHand);
            game.load(snap.fen || game.fen());
            board.position(snap.fen || game.fen());
            fenHistory = [game.fen()];
            updateCapturedPieces();
            applySnapshot(snap);
            if (myColor === 'w' || myColor === 'b') showPopup(`You are ${myColor === 'w' ? 'White' : 'Black'}.`);
        });

        socket.on('room_state', function(state) { applySnapshot(state); });

        socket.on('game_ready', function(state) {
            gameReady = true;
            $('#lobby-box').slideUp(180);
            $('#mini-state').text('The match has begun.');
            sfxStart.play();
            applySnapshot(state);
        });

        socket.on('standard_move', function(payload) {
            if (!payload || !payload.fen) return;
            game.load(payload.fen);
            board.position(payload.fen);
            if (fenHistory[fenHistory.length - 1] !== payload.fen) fenHistory.push(payload.fen);
            appendMove(payload);
            if (payload.san && payload.san.indexOf('x') !== -1) sfxCapture.play(); else sfxMove.play();
            updateCapturedPieces();
            updateTurnUI();
        });

        socket.on('spell_effect', function(payload) {
            if (!payload) return;
            clearSpellMode();
            if (payload.fen) {
                game.load(payload.fen);
                board.position(payload.fen);
                if (fenHistory[fenHistory.length - 1] !== payload.fen) fenHistory.push(payload.fen);
                updateCapturedPieces();
            }
            appendSpell((payload.log || payload.name || 'SPELL').toUpperCase());
            sfxSpell.play();
            if (!payload.consume_turn) showPopup('Expelliarmus! You move again.');
            updateTurnUI();
        });

        socket.on('action_denied', function(payload) {
            clearSpellMode();
            if (payload && payload.snapshot && payload.snapshot.fen) {
                game.load(payload.snapshot.fen);
                board.position(payload.snapshot.fen);
                if (fenHistory[fenHistory.length - 1] !== payload.snapshot.fen) fenHistory.push(payload.snapshot.fen);
                updateCapturedPieces();
            }
            updateTurnUI();
            showPopup(payload && payload.reason ? payload.reason : 'Action denied.');
        });

        socket.on('disconnect', function() {
            setStatus('Disconnected');
            $('#my-sub').text('Connection lost.');
            $('#opp-sub').text('Connection lost.');
            $('#board-overlay').css('display', 'flex');
            $('#board-overlay .overlay-title').text('Disconnected');
            $('#board-overlay .overlay-sub').text('Reconnect to continue the match.');
        });

        $('#help-btn').on('click', function() { $('#rules-modal').css('display', 'flex'); });
        $('#close-help').on('click', function() { $('#rules-modal').hide(); });

        $('#copy-btn').on('click', async function() {
            const input = document.getElementById('shareLink');
            try {
                await navigator.clipboard.writeText(input.value);
                $(this).text('Copied!');
                setTimeout(() => $(this).text('Copy Link'), 1400);
            } catch (e) {
                input.select();
                document.execCommand('copy');
                $(this).text('Copied!');
                setTimeout(() => $(this).text('Copy Link'), 1400);
            }
        });

        updateTurnUI();
        updateCapturedPieces();
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'> SERVER ONLINE. PORT: {port}')
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
