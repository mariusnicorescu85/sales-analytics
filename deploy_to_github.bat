@echo off
echo ========================================
echo Deploy Sales Dashboard to GitHub
echo ========================================
echo.

REM Check if git is installed
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in PATH
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

echo Step 1: Checking Git status...
echo.

REM Check if already a git repo
if exist .git (
    echo Git repository already initialized.
    git status
    echo.
    echo Do you want to:
    echo 1. Add all files and commit
    echo 2. Just push existing commits
    echo 3. Cancel
    set /p choice="Enter choice (1/2/3): "
    
    if "!choice!"=="1" (
        git add .
        set /p commit_msg="Enter commit message (or press Enter for default): "
        if "!commit_msg!"=="" set commit_msg=Update sales dashboard
        git commit -m "!commit_msg!"
    ) else if "!choice!"=="2" (
        echo Pushing to GitHub...
    ) else (
        echo Cancelled.
        pause
        exit /b 0
    )
) else (
    echo Initializing Git repository...
    git init
    git add .
    git commit -m "Initial commit - Sales Dashboard"
    echo.
    echo Git repository initialized and files committed.
    echo.
)

echo.
echo Step 2: Setting up GitHub remote...
echo.

REM Check if remote exists
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo No GitHub remote configured.
    echo.
    echo Please create a new repository on GitHub first:
    echo 1. Go to https://github.com/new
    echo 2. Create a new repository (don't initialize with README)
    echo 3. Copy the repository URL
    echo.
    set /p repo_url="Enter your GitHub repository URL (e.g., https://github.com/username/sales-dashboard.git): "
    
    if "!repo_url!"=="" (
        echo No URL provided. Exiting.
        pause
        exit /b 1
    )
    
    git remote add origin "!repo_url!"
    echo Remote added: !repo_url!
) else (
    git remote get-url origin
    echo Remote already configured.
)

echo.
echo Step 3: Pushing to GitHub...
echo.

git branch -M main
git push -u origin main

if errorlevel 1 (
    echo.
    echo ERROR: Failed to push to GitHub.
    echo.
    echo Common issues:
    echo - Repository doesn't exist on GitHub
    echo - Authentication required (use GitHub Desktop or configure Git credentials)
    echo - Network issues
    echo.
    echo You may need to:
    echo 1. Set up GitHub authentication
    echo 2. Use GitHub Desktop for easier pushing
    echo 3. Or manually push using: git push -u origin main
) else (
    echo.
    echo ========================================
    echo SUCCESS! Code pushed to GitHub
    echo ========================================
    echo.
    echo Next steps:
    echo 1. Go to https://share.streamlit.io
    echo 2. Sign in with GitHub
    echo 3. Click "New app"
    echo 4. Select your repository
    echo 5. Set main file to: dashboard.py
    echo 6. Click "Deploy"
    echo.
)

pause