# Deploy to Streamlit Cloud (5 Minutes)

## Step 1: Prepare Your Code

Your code is already ready! The following files are set up:
- ✅ `dashboard.py` - Main dashboard
- ✅ `requirements.txt` - Dependencies
- ✅ `.streamlit/config.toml` - Streamlit config
- ✅ `.gitignore` - Git ignore file

## Step 2: Create GitHub Repository

1. **Initialize Git (if not already done):**
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Sales Dashboard"
   ```

2. **Create a new repository on GitHub:**
   - Go to https://github.com/new
   - Name it: `sales-dashboard` (or any name)
   - Don't initialize with README
   - Click "Create repository"

3. **Push your code:**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/sales-dashboard.git
   git branch -M main
   git push -u origin main
   ```

## Step 3: Deploy to Streamlit Cloud

1. **Go to Streamlit Cloud:**
   - Visit https://share.streamlit.io
   - Sign in with your GitHub account

2. **Create New App:**
   - Click "New app" button
   - Select your repository: `YOUR_USERNAME/sales-dashboard`
   - Set Main file path: `dashboard.py`
   - App URL: `sales-dashboard` (or your choice)
   - Click "Deploy"

3. **Wait for deployment** (usually 1-2 minutes)

4. **Your app is live!** 🎉
   - URL: `https://sales-dashboard.streamlit.app`

## Step 4: Configure Airtable (Optional)

If you want to use Airtable sync:

1. **In Streamlit Cloud, go to your app settings**
2. **Click "Secrets"**
3. **Add your Airtable credentials:**
   ```toml
   AIRTABLE_TOKEN = "your_token_here"
   AIRTABLE_BASE_ID = "appFM5cdHTTI8IugV"
   AIRTABLE_TABLE_NAME = "Opatra Sales from July 2023"
   ```
4. **Save** - The app will automatically redeploy

## Step 5: Upload Your CSV Files

You have two options:

### Option A: Include CSVs in Repository (Simple)
- Add your CSV files to the repo
- They'll be available to the dashboard
- **Note:** Large files may slow down deployment

### Option B: Use Airtable Sync (Recommended)
- Use the Airtable sync feature in the dashboard
- No need to upload CSV files
- Always gets latest data

## Updating Your App

Whenever you push changes to GitHub:
1. Streamlit Cloud automatically detects changes
2. Automatically redeploys your app
3. Usually takes 1-2 minutes

## Troubleshooting

**"App failed to deploy"**
- Check that `dashboard.py` is in the root directory
- Verify `requirements.txt` has all dependencies
- Check the logs in Streamlit Cloud

**"Module not found"**
- Make sure all packages are in `requirements.txt`
- Check the deployment logs

**"CSV files not found"**
- Make sure CSV files are in the repository
- Or use Airtable sync instead

**"Airtable sync not working"**
- Check that secrets are set correctly
- Verify token has read access
- Check base ID and table name

## Next Steps

- Share your dashboard URL with your team
- Set up automatic syncing from Airtable
- Customize the theme in `.streamlit/config.toml`

## Cost

**Streamlit Cloud is FREE!** 🎉

- Unlimited apps
- Unlimited deployments
- Public repos = public apps (free)
- Private repos = private apps (requires Team plan, but you can keep it public for free)

---

**That's it! Your dashboard is now live on the internet!** 🚀