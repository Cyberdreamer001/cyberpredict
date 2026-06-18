from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt
import sqlite3
import os
import uuid
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import timedelta, datetime
import secrets

app = Flask(__name__)
CORS(app, origins="*")

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET", "cyberpredict-secret-2025")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)
jwt = JWTManager(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "cyberpredict.db")

GMAIL_USER = os.environ.get("GMAIL_USER", "cyberdreamer017@gmail.com")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "tyka vqsl xybo dxpk")
SITE_URL   = os.environ.get("SITE_URL", "https://cyberdreamer001.github.io/cyberpredict")
API_URL    = os.environ.get("API_URL",  "https://cyberpredict-api.onrender.com")

# ── UPLOADS FOLDER ────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── DB ────────────────────────────────────────────────────────────────────────
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
            is_verified INTEGER DEFAULT 0,
            verify_token TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS vip_requests (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            screenshot_path TEXT,
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
            odds_extra REAL,
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
    # Seed admin
    admin = db.execute("SELECT id FROM users WHERE email='admin@cyberpredict.com'").fetchone()
    if not admin:
        pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        db.execute("INSERT INTO users (id,name,email,phone,password_hash,is_admin,is_vip,is_verified) VALUES (?,?,?,?,?,1,1,1)",
                   (str(uuid.uuid4()), "Admin", "admin@cyberpredict.com", "08085137325", pw))
    db.commit()
    db.close()

init_db()

# ── EMAIL ─────────────────────────────────────────────────────────────────────
def send_email(to_email, subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"CyberPredict <{GMAIL_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def verification_email(name, email, token):
    link = f"{API_URL}/api/auth/verify/{token}"
    return send_email(email, "✅ Verify Your CyberPredict Account", f"""
    <div style="font-family:sans-serif;max-width:500px;margin:auto;background:#151515;color:#f0f0f0;border-radius:12px;overflow:hidden">
      <div style="background:#00a651;padding:24px;text-align:center">
        <h1 style="margin:0;color:#fff;font-size:24px">⚽ CyberPredict</h1>
      </div>
      <div style="padding:28px">
        <h2 style="color:#f0f0f0">Hi {name}! 👋</h2>
        <p style="color:#a0a0a0;line-height:1.6">Thanks for registering on CyberPredict. Click the button below to verify your email and activate your account.</p>
        <div style="text-align:center;margin:28px 0">
          <a href="{link}" style="background:#00a651;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:16px">✅ Verify My Email</a>
        </div>
        <p style="color:#666;font-size:12px">If you didn't register on CyberPredict, ignore this email.</p>
        <p style="color:#666;font-size:12px">Or copy this link: {link}</p>
      </div>
    </div>""")

def vip_pending_email(name, email):
    return send_email(email, "🔑 VIP Request Received — CyberPredict", f"""
    <div style="font-family:sans-serif;max-width:500px;margin:auto;background:#151515;color:#f0f0f0;border-radius:12px;overflow:hidden">
      <div style="background:#f5a623;padding:24px;text-align:center">
        <h1 style="margin:0;color:#000;font-size:24px">🔑 CyberPredict VIP</h1>
      </div>
      <div style="padding:28px">
        <h2 style="color:#f0f0f0">Hi {name}! 🎉</h2>
        <p style="color:#a0a0a0;line-height:1.6">We have received your VIP subscription request. Our team will verify your payment and activate your VIP access within <strong style="color:#f5a623">30 minutes</strong>.</p>
        <div style="background:#1e1e1e;border:1px solid rgba(245,166,35,.3);border-radius:8px;padding:16px;margin:20px 0">
          <p style="margin:0;color:#f5a623;font-weight:700">What happens next:</p>
          <p style="margin:8px 0 0;color:#a0a0a0;font-size:14px">1. Admin verifies your payment screenshot<br>2. Your VIP access is activated (30 days)<br>3. You get another email confirming activation</p>
        </div>
        <p style="color:#666;font-size:12px">Payment: OPAY — 8085137325 — Cyprian Nyuykonge Valentine</p>
      </div>
    </div>""")

def vip_approved_email(name, email, expires):
    return send_email(email, "🎉 VIP Access Activated — CyberPredict", f"""
    <div style="font-family:sans-serif;max-width:500px;margin:auto;background:#151515;color:#f0f0f0;border-radius:12px;overflow:hidden">
      <div style="background:#f5a623;padding:24px;text-align:center">
        <h1 style="margin:0;color:#000;font-size:24px">🎉 VIP Activated!</h1>
      </div>
      <div style="padding:28px">
        <h2 style="color:#f0f0f0">Congratulations {name}! 🏆</h2>
        <p style="color:#a0a0a0;line-height:1.6">Your VIP access has been activated! You can now access all premium picks and 5-odds games.</p>
        <div style="background:#1e1e1e;border:1px solid rgba(245,166,35,.3);border-radius:8px;padding:16px;margin:20px 0;text-align:center">
          <p style="margin:0;color:#f5a623;font-weight:700;font-size:18px">✅ VIP Active Until</p>
          <p style="margin:8px 0 0;color:#fff;font-size:22px;font-weight:900">{expires}</p>
        </div>
        <div style="text-align:center;margin:24px 0">
          <a href="{SITE_URL}" style="background:#f5a623;color:#000;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:16px">🔑 Access VIP Picks Now</a>
        </div>
      </div>
    </div>""")

# ── HELPERS ───────────────────────────────────────────────────────────────────
def rows_to_list(rows): return [dict(r) for r in rows]

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    data     = request.json
    name     = data.get("name","").strip()
    email    = data.get("email","").strip().lower()
    phone    = data.get("phone","").strip()
    password = data.get("password","")
    if not all([name, email, phone, password]):
        return jsonify({"error":"All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error":"Password must be at least 6 characters"}), 400
    db = get_db()
    if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        db.close()
        return jsonify({"error":"Email already registered"}), 409
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    uid     = str(uuid.uuid4())
    token   = secrets.token_urlsafe(32)
    db.execute("INSERT INTO users (id,name,email,phone,password_hash,verify_token,is_verified) VALUES (?,?,?,?,?,?,0)",
               (uid, name, email, phone, pw_hash, token))
    db.commit()
    db.close()
    # Send verification email
    sent = verification_email(name, email, token)
    return jsonify({
        "success": True,
        "message": "Account created! Please check your email to verify your account.",
        "email_sent": sent
    }), 201

@app.route("/api/auth/verify/<token>", methods=["GET"])
def verify_email(token):
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE verify_token=?", (token,)).fetchone()
    if not user:
        db.close()
        return f"""<html><body style="font-family:sans-serif;background:#0d0d0d;color:#f0f0f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="text-align:center"><div style="font-size:60px">❌</div><h2>Invalid or expired verification link.</h2>
        <a href="{SITE_URL}" style="color:#00a651">Go back to CyberPredict</a></div></body></html>""", 400
    db.execute("UPDATE users SET is_verified=1, verify_token=NULL WHERE id=?", (user["id"],))
    db.commit()
    db.close()
    return f"""<html><body style="font-family:sans-serif;background:#0d0d0d;color:#f0f0f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
    <div style="text-align:center;max-width:400px;padding:20px">
      <div style="font-size:60px">✅</div>
      <h2 style="color:#00a651">Email Verified!</h2>
      <p style="color:#a0a0a0">Your account is now active. You can log in to CyberPredict.</p>
      <a href="{SITE_URL}" style="display:inline-block;margin-top:16px;background:#00a651;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700">🔑 Login Now</a>
    </div></body></html>"""

@app.route("/api/auth/resend-verification", methods=["POST"])
def resend_verification():
    email = request.json.get("email","").strip().lower()
    db    = get_db()
    user  = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        db.close()
        return jsonify({"error":"Email not found"}), 404
    if user["is_verified"]:
        db.close()
        return jsonify({"error":"Email already verified"}), 400
    token = secrets.token_urlsafe(32)
    db.execute("UPDATE users SET verify_token=? WHERE email=?", (token, email))
    db.commit()
    db.close()
    verification_email(user["name"], email, token)
    return jsonify({"success": True, "message": "Verification email resent!"})

@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.json
    email    = data.get("email","").strip().lower()
    password = data.get("password","")
    db       = get_db()
    user     = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error":"Invalid email or password"}), 401
    if not user["is_verified"]:
        return jsonify({"error":"Please verify your email first. Check your inbox.", "needs_verification": True}), 403
    # Check VIP expiry
    is_vip = user["is_vip"]
    if is_vip and user["vip_expires"]:
        try:
            if datetime.strptime(user["vip_expires"], "%Y-%m-%d") < datetime.now():
                is_vip = 0
        except: pass
    token = create_access_token(identity=user["id"])
    return jsonify({"token": token, "user": {
        "id": user["id"], "name": user["name"], "email": user["email"],
        "is_vip": is_vip, "is_admin": user["is_admin"],
        "vip_expires": user["vip_expires"]
    }})

@app.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    if not user: return jsonify({"error":"Not found"}), 404
    is_vip = user["is_vip"]
    if is_vip and user["vip_expires"]:
        try:
            if datetime.strptime(user["vip_expires"], "%Y-%m-%d") < datetime.now():
                is_vip = 0
        except: pass
    return jsonify({"id": user["id"], "name": user["name"], "email": user["email"],
                    "is_vip": is_vip, "is_admin": user["is_admin"], "vip_expires": user["vip_expires"]})

# ── FREE PICKS ────────────────────────────────────────────────────────────────
@app.route("/api/picks/free", methods=["GET"])
def get_free_picks():
    date  = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    db    = get_db()
    picks = db.execute("SELECT * FROM free_picks WHERE match_date=? ORDER BY match_time", (date,)).fetchall()
    db.close()
    return jsonify(rows_to_list(picks))

@app.route("/api/picks/free", methods=["POST"])
@jwt_required()
def add_free_pick():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    d   = request.json
    pid = str(uuid.uuid4())
    db.execute("""INSERT INTO free_picks
        (id,league,home_team,away_team,match_time,match_date,pick,odds_home,odds_draw,odds_away,odds_extra,confidence)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, d["league"], d["home_team"], d["away_team"], d["match_time"], d["match_date"],
         d["pick"], d.get("odds_home"), d.get("odds_draw"), d.get("odds_away"),
         d.get("odds_extra"), d.get("confidence",70)))
    db.commit(); db.close()
    return jsonify({"success":True,"id":pid})

@app.route("/api/picks/free/<pid>", methods=["DELETE"])
@jwt_required()
def delete_free_pick(pid):
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    db.execute("DELETE FROM free_picks WHERE id=?", (pid,))
    db.commit(); db.close()
    return jsonify({"success":True})

@app.route("/api/picks/free/<pid>/result", methods=["PUT"])
@jwt_required()
def update_free_result(pid):
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    db.execute("UPDATE free_picks SET result=? WHERE id=?", (request.json.get("result"), pid))
    db.commit(); db.close()
    return jsonify({"success":True})

# ── VIP PICKS ─────────────────────────────────────────────────────────────────
@app.route("/api/picks/vip", methods=["GET"])
@jwt_required()
def get_vip_picks():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_vip,is_admin,vip_expires FROM users WHERE id=?", (uid,)).fetchone()
    if not user: db.close(); return jsonify({"error":"Not found"}), 404
    ok = bool(user["is_admin"])
    if user["is_vip"] and not ok:
        try:
            ok = not user["vip_expires"] or datetime.strptime(user["vip_expires"],"%Y-%m-%d") >= datetime.now()
        except: ok = True
    if not ok: db.close(); return jsonify({"error":"VIP subscription required"}), 403
    date  = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    picks = db.execute("SELECT * FROM vip_picks WHERE match_date=? ORDER BY match_time", (date,)).fetchall()
    db.close()
    return jsonify(rows_to_list(picks))

@app.route("/api/picks/vip", methods=["POST"])
@jwt_required()
def add_vip_pick():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    d   = request.json
    pid = str(uuid.uuid4())
    db.execute("""INSERT INTO vip_picks
        (id,league,home_team,away_team,match_time,match_date,pick,analysis,combined_odds,confidence)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (pid, d["league"], d["home_team"], d["away_team"], d["match_time"], d["match_date"],
         d["pick"], d.get("analysis",""), d.get("combined_odds",5.0), d.get("confidence",85)))
    db.commit(); db.close()
    return jsonify({"success":True,"id":pid})

@app.route("/api/picks/vip/<pid>", methods=["DELETE"])
@jwt_required()
def delete_vip_pick(pid):
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    db.execute("DELETE FROM vip_picks WHERE id=?", (pid,))
    db.commit(); db.close()
    return jsonify({"success":True})

# ── ACCUMULATORS ──────────────────────────────────────────────────────────────
@app.route("/api/accumulators", methods=["GET"])
def get_accumulators():
    import json
    date  = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    db    = get_db()
    accas = db.execute("SELECT * FROM accumulators WHERE match_date=? AND is_vip=0", (date,)).fetchall()
    db.close()
    result = []
    for a in accas:
        d = dict(a); d["picks"] = json.loads(d["picks"]); result.append(d)
    return jsonify(result)

@app.route("/api/accumulators", methods=["POST"])
@jwt_required()
def add_accumulator():
    import json
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    d   = request.json
    aid = str(uuid.uuid4())
    db.execute("INSERT INTO accumulators (id,title,total_odds,picks,is_vip,match_date) VALUES (?,?,?,?,?,?)",
               (aid, d["title"], d["total_odds"], json.dumps(d["picks"]), d.get("is_vip",0), d["match_date"]))
    db.commit(); db.close()
    return jsonify({"success":True,"id":aid})

# ── VIP SUBSCRIPTION ──────────────────────────────────────────────────────────
@app.route("/api/vip/request", methods=["POST"])
@jwt_required()
def vip_request():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user: db.close(); return jsonify({"error":"Not found"}), 404
    if user["is_vip"]: db.close(); return jsonify({"error":"You already have VIP access"}), 400

    # Check if already pending
    existing = db.execute("SELECT id FROM vip_requests WHERE user_id=? AND status='pending'", (uid,)).fetchone()
    if existing: db.close(); return jsonify({"error":"You already have a pending VIP request"}), 400

    # Handle screenshot (base64)
    screenshot_path = None
    screenshot_b64  = request.json.get("screenshot")
    if screenshot_b64:
        try:
            header, data = screenshot_b64.split(",", 1)
            ext  = "jpg" if "jpeg" in header else "png"
            fname = f"{uuid.uuid4()}.{ext}"
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(data))
            screenshot_path = fname
        except Exception as e:
            print(f"Screenshot save error: {e}")

    rid = str(uuid.uuid4())
    db.execute("INSERT INTO vip_requests (id,user_id,name,email,phone,screenshot_path,status) VALUES (?,?,?,?,?,?,?)",
               (rid, uid, user["name"], user["email"], user["phone"], screenshot_path, "pending"))
    db.commit(); db.close()

    # Notify user
    vip_pending_email(user["name"], user["email"])
    return jsonify({"success":True, "message":"Request submitted! We'll activate your VIP within 30 minutes after verifying your payment."})

@app.route("/api/vip/requests", methods=["GET"])
@jwt_required()
def get_vip_requests():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    reqs = db.execute("SELECT * FROM vip_requests ORDER BY created_at DESC").fetchall()
    db.close()
    result = []
    for r in reqs:
        d = dict(r)
        if d["screenshot_path"]:
            d["screenshot_url"] = f"{API_URL}/api/vip/screenshot/{d['screenshot_path']}"
        result.append(d)
    return jsonify(result)

@app.route("/api/vip/screenshot/<filename>")
@jwt_required()
def get_screenshot(filename):
    from flask import send_from_directory
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    if not user or not user["is_admin"]:
        return jsonify({"error":"Admin only"}), 403
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/api/vip/approve", methods=["POST"])
@jwt_required()
def approve_vip():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    req_id = request.json.get("request_id")
    req    = db.execute("SELECT * FROM vip_requests WHERE id=?", (req_id,)).fetchone()
    if not req: db.close(); return jsonify({"error":"Request not found"}), 404
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    db.execute("UPDATE users SET is_vip=1, vip_expires=? WHERE email=?", (expiry, req["email"]))
    db.execute("UPDATE vip_requests SET status='approved' WHERE id=?", (req_id,))
    db.commit(); db.close()
    vip_approved_email(req["name"], req["email"], expiry)
    return jsonify({"success":True, "message":f"VIP activated for {req['email']} until {expiry}"})

@app.route("/api/vip/reject", methods=["POST"])
@jwt_required()
def reject_vip():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    req_id = request.json.get("request_id")
    db.execute("UPDATE vip_requests SET status='rejected' WHERE id=?", (req_id,))
    db.commit(); db.close()
    return jsonify({"success":True})

@app.route("/api/vip/revoke", methods=["POST"])
@jwt_required()
def revoke_vip():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    email = request.json.get("email","").lower()
    db.execute("UPDATE users SET is_vip=0, vip_expires=NULL WHERE email=?", (email,))
    db.commit(); db.close()
    return jsonify({"success":True})

# ── ADMIN USERS ───────────────────────────────────────────────────────────────
@app.route("/api/admin/users", methods=["GET"])
@jwt_required()
def get_users():
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if not user or not user["is_admin"]:
        db.close(); return jsonify({"error":"Admin only"}), 403
    users = db.execute("SELECT id,name,email,phone,is_vip,is_admin,is_verified,vip_expires,created_at FROM users ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify(rows_to_list(users))

# ── RESULTS ───────────────────────────────────────────────────────────────────
@app.route("/api/results", methods=["GET"])
def get_results():
    db   = get_db()
    free = db.execute("SELECT *,'free' as type FROM free_picks WHERE result!='pending' ORDER BY match_date DESC,match_time DESC LIMIT 20").fetchall()
    db.close()
    return jsonify(rows_to_list(free))

@app.route("/")
def health():
    return jsonify({"status":"CyberPredict API running","version":"2.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
