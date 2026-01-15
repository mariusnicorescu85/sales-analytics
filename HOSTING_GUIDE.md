# Hosting Guide for Sales Dashboard

## ❌ Vercel - Not Recommended for Streamlit

Vercel is designed for static sites and serverless functions. Streamlit requires:
- A Python runtime environment
- Persistent server process
- WebSocket connections
- File system access for CSV files

**Vercel doesn't support Streamlit apps natively.**

## ✅ Best Hosting Options for Streamlit

### Option 1: Streamlit Cloud (Recommended - FREE) ⭐

**Best for:** Quick deployment, zero cost, automatic updates

**Steps:**
1. Push your code to GitHub
2. Go to https://share.streamlit.io
3. Sign in with GitHub
4. Click "New app"
5. Select your repository
6. Set main file to `dashboard.py`
7. Deploy!

**Pros:**
- ✅ Completely free
- ✅ Automatic deployments from GitHub
- ✅ Built specifically for Streamlit
- ✅ Easy to set up
- ✅ Handles all infrastructure

**Cons:**
- ⚠️ Public repos are public apps (or pay for private)
- ⚠️ Limited customization

**Note:** For Airtable sync, you'll need to set environment variables in Streamlit Cloud settings.

---

### Option 2: Railway (Recommended - Easy & Affordable)

**Best for:** Private apps, easy deployment, good free tier

**Steps:**
1. Go to https://railway.app
2. Sign up with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Select your repository
6. Railway auto-detects Python
7. Add environment variables if needed
8. Deploy!

**Pros:**
- ✅ $5/month free credit (usually enough)
- ✅ Private by default
- ✅ Easy deployment
- ✅ Auto-deploys from GitHub
- ✅ Good documentation

**Cons:**
- ⚠️ Costs money after free tier (but very affordable)

---

### Option 3: Render (Good Free Option)

**Best for:** Free hosting with some limitations

**Steps:**
1. Go to https://render.com
2. Sign up
3. Click "New" → "Web Service"
4. Connect GitHub repo
5. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0`
6. Deploy!

**Pros:**
- ✅ Free tier available
- ✅ Auto-deploys from GitHub
- ✅ Good for small apps

**Cons:**
- ⚠️ Free tier spins down after inactivity
- ⚠️ Slower cold starts

---

### Option 4: Heroku (Classic Option)

**Best for:** Established platform, lots of resources

**Steps:**
1. Create `Procfile` with: `web: streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0`
2. Push to GitHub
3. Connect to Heroku
4. Deploy

**Pros:**
- ✅ Well-established platform
- ✅ Good documentation

**Cons:**
- ⚠️ No free tier anymore
- ⚠️ More expensive than alternatives

---

## 📋 Pre-Deployment Checklist

Before deploying anywhere, make sure:

1. **All dependencies in requirements.txt:**
   ```
   streamlit>=1.28.0
   pandas>=2.0.0
   plotly>=5.17.0
   numpy>=1.24.0
   scipy>=1.10.0
   pyairtable>=2.3.0
   ```

2. **Create `.streamlit/config.toml` (optional):**
   ```toml
   [server]
   port = 8501
   enableCORS = false
   enableXsrfProtection = false
   ```

3. **Add `.gitignore`:**
   ```
   __pycache__/
   *.pyc
   .env
   *.csv
   .streamlit/secrets.toml
   ```

4. **For Airtable sync, set environment variables:**
   - `AIRTABLE_TOKEN`
   - `AIRTABLE_BASE_ID`
   - `AIRTABLE_TABLE_NAME`

---

## 🔄 Alternative: Convert to Static Site for Vercel

If you really want to use Vercel, you'd need to:

1. **Convert the dashboard to a static HTML/JavaScript app**
   - Use the existing `dashboard.html` file
   - Host CSV files elsewhere (GitHub, S3, etc.)
   - Use client-side JavaScript for all processing

2. **Or use Vercel Serverless Functions**
   - Create API endpoints for data processing
   - Use Next.js or similar framework
   - More complex, requires significant rewrite

**This is NOT recommended** - it's much easier to use Streamlit Cloud or Railway.

---

## 🚀 Quick Start: Streamlit Cloud (5 minutes)

1. **Prepare your repo:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/sales-dashboard.git
   git push -u origin main
   ```

2. **Go to Streamlit Cloud:**
   - Visit https://share.streamlit.io
   - Sign in with GitHub
   - Click "New app"
   - Select your repo
   - Main file: `dashboard.py`
   - Click "Deploy"

3. **Set secrets (for Airtable):**
   - In app settings, go to "Secrets"
   - Add:
     ```
     AIRTABLE_TOKEN=your_token
     AIRTABLE_BASE_ID=your_base_id
     ```

4. **Done!** Your app is live at `https://your-app.streamlit.app`

---

## 💡 Recommendation

**Use Streamlit Cloud** - it's free, easy, and designed specifically for Streamlit apps. Perfect for your use case!

If you need privacy or more control, **Railway** is the next best option.