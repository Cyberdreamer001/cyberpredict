from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt
import sqlite3
import os
import uuid
from datetime import timedelta, datetime

app = Flask(__name__)
CORS(app, origins="*")

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET", "cyberpredict-secret-2025-change-in-prod")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)
jwt = JWTManager(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "cyberpredict.db")

# ── DB ──────────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_expires TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS vip_requests (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS free_picks (
            id TEXT PRIMARY KEY,
            league TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            match_time TEXT NOT NULL,
            match_date TEXT NOT NULL,
            pick TEXT NOT NULL,
            odds_home REAL,
            odds_draw REAL,
            odds_away REAL,
            odds_extra TEXT,
            confidence INTEGER DEFAULT 70,
            result TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS vip_picks (
            id TEXT PRIMARY KEY,
            league TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            match_time TEXT NOT NULL,
            match_date TEXT NOT NULL,
            pick TEXT NOT NULL,
            analysis TEXT,
            combined_odds REAL,
            confidence INTEGER DEFAULT 85,
            result TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS accumulators (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            total_odds REAL NOT NULL,
            picks TEXT NOT NULL,
            is_vip INTEGER DEFAULT 0,
            match_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Seed admin account
    admin = db.execute("SELECT id FROM users WHERE email = 'admin@cyberpredict.com'").fetchone()
    if not admin:
        pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        db.execute("INSERT INTO users (id,name,email,phone,password_hash,is_admin,is_vip) VALUES (?,?,?,?,?,1,1)",
                   (str(uuid.uuid4()), "Admin", "admin@cyberpredict.com", "08085137325", pw))
    db.commit()
    db.close()

init_db()

# ── HELPERS ──────────────────────────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ── AUTH ─────────────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name","").strip()
    email = data.get("email","").strip().lower()
    phone = data.get("phone","").strip()
    password = data.get("password","")
    if not all([name, email, phone, password]):
        return jsonify({"error": "All fields required"}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Email already registered"}), 409
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    uid = str(uuid.uuid4())
    db.execute("INSERT INTO users (id,name,email,phone,password_hash) VALUES (?,?,?,?,?)",
               (uid, name, email, phone, pw_hash))
    db.commit()
    db.close()
    token = create_access_token(identity=uid)
    return jsonify({"token": token, "user": {"id": uid, "name": name, "email": email, "is_vip": 0, "is_admin": 0}})

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email","").strip().lower()
    password = data.get("password","")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Invalid email or password"}), 401
    token = create_access_token(identity=user["id"])
    return jsonify({"token": token, "user": {
        "id": user["id"], "name": user["name"], "email": user["email"],
        "is_vip": user["is_vip"], "is_admin": user["is_admin"],
        "vip_expires": user["vip_expires"]
    }})

@app.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"id": user["id"], "name": user["name"], "email": user["email"],
                    "is_vip": user["is_vip"], "is_admin": user["is_admin"],
                    "vip_expires": user["vip_expires"]})

# ── FREE PICKS ────────────────────────────────────────────────────────────────
@app.route("/api/picks/free", methods=["GET"])
def get_free_picks():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    db = get_db()
    picks = db.execute("SELECT * FROM free_picks WHERE match_date=? ORDER BY match_time", (date,)).fetchall()
    db.close()
    return jsonify(rows_to_list(picks))

@app.route("/api/picks/free", methods=["POST"])
@jwt_required()
def add_free_pick():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    data = request.json
    pid = str(uuid.uuid4())
    db.execute("""INSERT INTO free_picks (id,league,home_team,away_team,match_time,match_date,pick,
                  odds_home,odds_draw,odds_away,odds_extra,confidence)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
               (pid, data["league"], data["home_team"], data["away_team"],
                data["match_time"], data["match_date"], data["pick"],
                data.get("odds_home"), data.get("odds_draw"), data.get("odds_away"),
                data.get("odds_extra"), data.get("confidence", 70)))
    db.commit()
    db.close()
    return jsonify({"success": True, "id": pid})

@app.route("/api/picks/free/<pid>", methods=["DELETE"])
@jwt_required()
def delete_free_pick(pid):
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    db.execute("DELETE FROM free_picks WHERE id=?", (pid,))
    db.commit()
    db.close()
    return jsonify({"success": True})

@app.route("/api/picks/free/<pid>/result", methods=["PUT"])
@jwt_required()
def update_free_result(pid):
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    result = request.json.get("result")
    db.execute("UPDATE free_picks SET result=? WHERE id=?", (result, pid))
    db.commit()
    db.close()
    return jsonify({"success": True})

# ── VIP PICKS ─────────────────────────────────────────────────────────────────
@app.route("/api/picks/vip", methods=["GET"])
@jwt_required()
def get_vip_picks():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_vip, is_admin, vip_expires FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        db.close()
        return jsonify({"error": "Not found"}), 404
    # Check VIP still valid
    is_valid_vip = user["is_admin"] == 1
    if user["is_vip"] == 1 and user["vip_expires"]:
        try:
            exp = datetime.strptime(user["vip_expires"], "%Y-%m-%d")
            is_valid_vip = is_valid_vip or exp >= datetime.now()
        except:
            pass
    elif user["is_vip"] == 1:
        is_valid_vip = True
    if not is_valid_vip:
        db.close()
        return jsonify({"error": "VIP subscription required"}), 403
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    picks = db.execute("SELECT * FROM vip_picks WHERE match_date=? ORDER BY match_time", (date,)).fetchall()
    db.close()
    return jsonify(rows_to_list(picks))

@app.route("/api/picks/vip", methods=["POST"])
@jwt_required()
def add_vip_pick():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    data = request.json
    pid = str(uuid.uuid4())
    db.execute("""INSERT INTO vip_picks (id,league,home_team,away_team,match_time,match_date,pick,
                  analysis,combined_odds,confidence)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (pid, data["league"], data["home_team"], data["away_team"],
                data["match_time"], data["match_date"], data["pick"],
                data.get("analysis",""), data.get("combined_odds", 5.0),
                data.get("confidence", 85)))
    db.commit()
    db.close()
    return jsonify({"success": True, "id": pid})

@app.route("/api/picks/vip/<pid>", methods=["DELETE"])
@jwt_required()
def delete_vip_pick(pid):
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    db.execute("DELETE FROM vip_picks WHERE id=?", (pid,))
    db.commit()
    db.close()
    return jsonify({"success": True})

# ── ACCUMULATORS ──────────────────────────────────────────────────────────────
@app.route("/api/accumulators", methods=["GET"])
def get_accumulators():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    db = get_db()
    accas = db.execute("SELECT * FROM accumulators WHERE match_date=? AND is_vip=0", (date,)).fetchall()
    db.close()
    import json
    result = []
    for a in accas:
        d = dict(a)
        d["picks"] = json.loads(d["picks"])
        result.append(d)
    return jsonify(result)

@app.route("/api/accumulators", methods=["POST"])
@jwt_required()
def add_accumulator():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    import json
    data = request.json
    aid = str(uuid.uuid4())
    db.execute("INSERT INTO accumulators (id,title,total_odds,picks,is_vip,match_date) VALUES (?,?,?,?,?,?)",
               (aid, data["title"], data["total_odds"], json.dumps(data["picks"]),
                data.get("is_vip", 0), data["match_date"]))
    db.commit()
    db.close()
    return jsonify({"success": True, "id": aid})

# ── VIP SUBSCRIPTION REQUESTS ─────────────────────────────────────────────────
@app.route("/api/vip/request", methods=["POST"])
def vip_request():
    data = request.json
    name = data.get("name","").strip()
    email = data.get("email","").strip().lower()
    phone = data.get("phone","").strip()
    if not all([name, email, phone]):
        return jsonify({"error": "All fields required"}), 400
    db = get_db()
    rid = str(uuid.uuid4())
    db.execute("INSERT INTO vip_requests (id,name,email,phone) VALUES (?,?,?,?)",
               (rid, name, email, phone))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Request submitted. VIP will be activated within 30 minutes after payment confirmation."})

@app.route("/api/vip/requests", methods=["GET"])
@jwt_required()
def get_vip_requests():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    requests_ = db.execute("SELECT * FROM vip_requests ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify(rows_to_list(requests_))

@app.route("/api/vip/approve", methods=["POST"])
@jwt_required()
def approve_vip():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    data = request.json
    email = data.get("email","").lower()
    # Calculate expiry 30 days from now
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    db.execute("UPDATE users SET is_vip=1, vip_expires=? WHERE email=?", (expiry, email))
    db.execute("UPDATE vip_requests SET status='approved' WHERE email=?", (email,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": f"VIP activated for {email} until {expiry}"})

@app.route("/api/vip/revoke", methods=["POST"])
@jwt_required()
def revoke_vip():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    email = request.json.get("email","").lower()
    db.execute("UPDATE users SET is_vip=0, vip_expires=NULL WHERE email=?", (email,))
    db.commit()
    db.close()
    return jsonify({"success": True})

# ── ADMIN USERS ───────────────────────────────────────────────────────────────
@app.route("/api/admin/users", methods=["GET"])
@jwt_required()
def get_users():
    uid = get_jwt_identity()
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close()
        return jsonify({"error": "Admin only"}), 403
    users = db.execute("SELECT id,name,email,phone,is_vip,is_admin,vip_expires,created_at FROM users ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify(rows_to_list(users))

# ── RESULTS ───────────────────────────────────────────────────────────────────
@app.route("/api/results", methods=["GET"])
def get_results():
    db = get_db()
    free = db.execute("SELECT *,'free' as type FROM free_picks WHERE result != 'pending' ORDER BY match_date DESC, match_time DESC LIMIT 20").fetchall()
    db.close()
    return jsonify(rows_to_list(free))

@app.route("/")
def health():
    return jsonify({"status": "CyberPredict API running", "version": "1.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
