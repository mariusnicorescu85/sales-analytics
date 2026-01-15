# ✅ Deployment Checklist

Follow these steps to deploy your dashboard to Streamlit Cloud:

## Pre-Deployment

- [ ] All required files are present:
  - [x] `dashboard.py` - Main dashboard file
  - [x] `requirements.txt` - Dependencies
  - [x] `.streamlit/config.toml` - Streamlit config
  - [x] `.gitignore` - Git ignore rules
  - [x] `README.md` - Project documentation

- [ ] Test locally:
  - [ ] Dashboard runs without errors: `streamlit run dashboard.py`
  - [ ] All tabs load correctly
  - [ ] Filters work properly
  - [ ] Charts display correctly

## GitHub Setup

- [ ] Create GitHub account (if you don't have one): https://github.com/signup
- [ ] Create new repository:
  - Go to https://github.com/new
  - Repository name: `sales-dashboard` (or your choice)
  - Description: "Sales Analytics Dashboard"
  - Visibility: Public (free) or Private (requires Team plan)
  - **Don't** initialize with README, .gitignore, or license
  - Click "Create repository"

## Push Code to GitHub

**Option 1: Use the helper script (Windows)**
- [ ] Double-click `deploy_to_github.bat`
- [ ] Follow the prompts
- [ ] Enter your GitHub repository URL when asked

**Option 2: Manual Git commands**
```bash
git init
git add .
git commit -m "Initial commit - Sales Dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sales-dashboard.git
git push -u origin main
```

- [ ] Verify code is on GitHub (visit your repository URL)

## Deploy to Streamlit Cloud

- [ ] Go to https://share.streamlit.io
- [ ] Sign in with GitHub
- [ ] Click "New app"
- [ ] Fill in:
  - Repository: Select your `sales-dashboard` repo
  - Branch: `main`
  - Main file path: `dashboard.py`
  - App URL: `sales-dashboard` (or your choice)
- [ ] Click "Deploy"
- [ ] Wait for deployment (1-2 minutes)

## Post-Deployment

- [ ] Test your live app:
  - Visit: `https://sales-dashboard.streamlit.app` (or your URL)
  - Check all tabs load
  - Test filters
  - Verify charts display

- [ ] Configure Airtable (if using):
  - Go to app settings → Secrets
  - Add:
    ```
    AIRTABLE_TOKEN = "your_token"
    AIRTABLE_BASE_ID = "appFM5cdHTTI8IugV"
    AIRTABLE_TABLE_NAME = "Opatra Sales from July 2023"
    ```
  - Save (app will redeploy)

- [ ] Share your dashboard:
  - Copy the URL
  - Share with your team
  - Bookmark for easy access

## Troubleshooting

**If deployment fails:**
- [ ] Check that `dashboard.py` is in the root directory
- [ ] Verify `requirements.txt` has all packages
- [ ] Check deployment logs in Streamlit Cloud
- [ ] Ensure CSV files are in the repository (if not using Airtable)

**If app loads but shows errors:**
- [ ] Check that CSV files are in the repo
- [ ] Verify file names match exactly (case-sensitive)
- [ ] Check the logs in Streamlit Cloud

**If Airtable sync doesn't work:**
- [ ] Verify secrets are set correctly
- [ ] Check token has read access
- [ ] Verify base ID and table name are correct

## Future Updates

When you make changes:
- [ ] Update code locally
- [ ] Test locally
- [ ] Commit and push to GitHub:
  ```bash
  git add .
  git commit -m "Your update message"
  git push
  ```
- [ ] Streamlit Cloud auto-deploys (usually 1-2 minutes)

## ✅ You're Done!

Your dashboard is now live and accessible from anywhere!

**Your app URL:** `https://sales-dashboard.streamlit.app`

---

**Need help?** Check:
- `DEPLOY_STREAMLIT_CLOUD.md` - Detailed deployment guide
- `HOSTING_GUIDE.md` - Alternative hosting options
- Streamlit Cloud docs: https://docs.streamlit.io/streamlit-community-cloud