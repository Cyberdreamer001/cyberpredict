# CyberPredict — Football Prediction Website
Full-stack football prediction site with free tips, VIP picks, user accounts, and admin panel.

---

## 🗂️ PROJECT STRUCTURE
```
cyberpredict/
├── backend/          ← Python/Flask API server
│   ├── app.py        ← Main server file
│   ├── requirements.txt
│   ├── Procfile
│   └── render.yaml
└── frontend/
    └── index.html    ← Full website (single file)
```

---

## 🚀 DEPLOYMENT GUIDE (Free — Render + GitHub Pages)

### STEP 1 — Create a GitHub Account
Go to https://github.com and create a free account if you don't have one.

### STEP 2 — Upload Your Files to GitHub
1. Go to https://github.com/new
2. Name the repo: `cyberpredict`
3. Set it to **Public**
4. Click **Create repository**
5. Upload all files from the `backend/` folder into the repo
6. Upload `frontend/index.html` into the same repo (or a separate folder called `frontend/`)

### STEP 3 — Deploy the Backend on Render (Free)
1. Go to https://render.com and sign up with your GitHub account
2. Click **New** → **Web Service**
3. Connect your `cyberpredict` GitHub repo
4. Fill in these settings:
   - **Name:** cyberpredict-api
   - **Root Directory:** backend
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Under **Environment Variables**, add:
   - Key: `JWT_SECRET` → Value: any random long string (e.g. `MySecretKey2025CyberPredict`)
6. Click **Create Web Service**
7. Wait 2-3 minutes. You'll get a URL like: `https://cyberpredict-api.onrender.com`
8. **Copy this URL** — you need it for Step 5

### STEP 4 — Host the Frontend on GitHub Pages (Free)
1. In your GitHub repo, go to **Settings** → **Pages**
2. Under **Source**, select **main branch** → `/frontend` folder (or root if you put index.html there)
3. Click **Save**
4. Your site will be live at: `https://yourusername.github.io/cyberpredict`

### STEP 5 — Connect Frontend to Backend
1. Open `frontend/index.html` in a text editor (Notepad, VS Code, etc.)
2. Find this line near the top of the `<script>` section:
   ```js
   const API = window.location.hostname === 'localhost' ...
     : ''; // same origin in production
   ```
3. Change the `''` to your Render URL:
   ```js
   : 'https://cyberpredict-api.onrender.com'
   ```
4. Save the file and re-upload it to GitHub
5. GitHub Pages will automatically update your live site

---

## 🔑 ADMIN LOGIN
After deployment, log in with:
- **Email:** admin@cyberpredict.com
- **Password:** admin123

⚠️ **IMPORTANT:** Change the admin password immediately after first login by contacting support or editing the DB.

---

## 💰 HOW VIP SUBSCRIPTION WORKS
1. A user visits the site and clicks **Subscribe to VIP**
2. They see your payment details (OPAY - 8085137325 - Cyprian Nyuykonge Valentine)
3. They send ₦10,000 and fill in their name, email, phone
4. You receive the notification and **verify payment in your OPAY app**
5. You log in as Admin → go to **Admin Panel** → see the request → click **✅ Approve**
6. The user's account is instantly upgraded to VIP for 30 days
7. They can now see all VIP picks

---

## ⚙️ HOW TO USE THE ADMIN PANEL
1. Log in with admin credentials
2. The **Admin** tab appears in the navigation
3. **Add Free Pick** — enter match details, odds, your pick → click Add
4. **Add VIP Pick** — enter the 5-odds game, full analysis → click Add
5. **Add Accumulator** — enter title, total odds, and picks one per line as:
   `Man City vs Arsenal | Home Win | 1.75`
6. **Approve VIP requests** — shown at the top of the admin panel
7. **Manage users** — view all registered users, give or revoke VIP

---

## 🛠️ LOCAL TESTING (Optional)
To test on your computer before deploying:

1. Install Python from https://python.org
2. Open terminal/command prompt in the `backend/` folder
3. Run: `pip install -r requirements.txt`
4. Run: `python app.py`
5. Server starts at http://localhost:5000
6. Open `frontend/index.html` directly in your browser
7. It will automatically connect to localhost

---

## 📱 FEATURES SUMMARY
- ✅ Free tips with odds, confidence bars, match cards
- ✅ Accumulator section with potential winnings calculator
- ✅ VIP section locked behind real subscription
- ✅ User registration & login (JWT secured)
- ✅ Admin panel to add/delete picks
- ✅ VIP request system with manual bank transfer approval
- ✅ Results tracker
- ✅ SportyBet-style dark green design
- ✅ Mobile responsive
- ✅ SQLite database (no extra setup needed)

---

## 🆘 NEED HELP?
If you get stuck at any step, the most common issues are:
- **CORS error** — Make sure your Render URL is correct in index.html
- **Server not starting** — Check that all files are uploaded correctly
- **VIP not unlocking** — User must be registered with the same email they submitted in the VIP form
