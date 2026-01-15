# 🚀 Quick Deploy Guide (5 Minutes)

## Step 1: Push to GitHub (2 minutes)

**Option A: Use the helper script**
1. Double-click `deploy_to_github.bat`
2. Follow the prompts
3. Enter your GitHub repo URL when asked

**Option B: Manual (if you prefer)**
```bash
git init
git add .
git commit -m "Sales Dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sales-dashboard.git
git push -u origin main
```

**Don't have a GitHub repo yet?**
1. Go to https://github.com/new
2. Create a new repository (name it `sales-dashboard`)
3. **Don't** initialize with README
4. Copy the repository URL
5. Use it in the script above

## Step 2: Deploy to Streamlit Cloud (2 minutes)

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click **"New app"**
4. Fill in:
   - **Repository:** Select `sales-dashboard` (or your repo name)
   - **Branch:** `main`
   - **Main file path:** `dashboard.py`
   - **App URL:** `sales-dashboard` (or your choice)
5. Click **"Deploy"**
6. Wait 1-2 minutes

## Step 3: Done! 🎉

Your dashboard is live at:
**`https://sales-dashboard.streamlit.app`**

## Optional: Add Airtable Sync

1. In Streamlit Cloud, go to your app
2. Click **⚙️ Settings** → **Secrets**
3. Add:
   ```
   AIRTABLE_TOKEN = "your_token_here"
   AIRTABLE_BASE_ID = "appFM5cdHTTI8IugV"
   AIRTABLE_TABLE_NAME = "Opatra Sales from July 2023"
   ```
4. Save (auto-redeploys)

## Updating Your Dashboard

Whenever you make changes:
```bash
git add .
git commit -m "Your update"
git push
```

Streamlit Cloud automatically redeploys! ✨

---

**That's it!** Your dashboard is now accessible from anywhere in the world! 🌍