# 🚀 Complete Deployment Guide

## 📋 Choose Your Deployment Platform

I recommend these platforms (all have free tiers):

1. **Render.com** ⭐ (Easiest, Recommended)
2. **Railway.app** (Fast, modern)
3. **Vercel** (Frontend only - needs separate backend)
4. **Docker/VPS** (Full control)

---

## 🎯 Option 1: Render.com (RECOMMENDED - Easiest)

### Step 1: Prepare Your Repository

Your code is already on GitHub at: `https://github.com/RahulSGosavi/test-interiorr-ai.git` ✅

### Step 2: Sign Up on Render

1. Go to https://render.com
2. Sign up with your GitHub account
3. Authorize Render to access your repositories

### Step 3: Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your repository: `RahulSGosavi/test-interiorr-ai`
3. Configure the service:

```
Name: annotation-ai-suite
Region: Choose closest to you
Branch: main
Root Directory: (leave blank)
Environment: Docker
Plan: Free (or Starter for better performance)
```

### Step 4: Set Environment Variables

Click **"Advanced"** and add these environment variables:

```env
SECRET_KEY=your-super-secret-key-change-this-123456789
ACCESS_TOKEN_EXPIRE_MINUTES=43200
CORS_ORIGINS=*
UPLOAD_DIR=/opt/render/project/src/backend/uploads
PORT=10000
NODE_ENV=production
```

**Generate a secure SECRET_KEY:**
- Windows PowerShell: `[System.Convert]::ToBase64String([System.Security.Cryptography.RNGCryptoServiceProvider]::new().GetBytes(32))`
- Online: https://www.grc.com/passwords.htm

### Step 5: Add Persistent Disk (for file uploads)

1. Scroll down to **"Disks"**
2. Click **"Add Disk"**
3. Configure:
   ```
   Name: uploads
   Mount Path: /opt/render/project/src/backend/uploads
   Size: 1 GB (free tier allows up to 1GB)
   ```

### Step 6: Deploy!

1. Click **"Create Web Service"**
2. Wait 5-10 minutes for the build to complete
3. Your app will be live at: `https://annotation-ai-suite-xxxx.onrender.com`

### Step 7: Test Your Deployment

1. Visit your Render URL
2. You should see the login page
3. Create an account and test the features!

---

## 🚂 Option 2: Railway.app

### Step 1: Sign Up

1. Go to https://railway.app
2. Sign up with GitHub

### Step 2: Deploy from GitHub

1. Click **"New Project"**
2. Choose **"Deploy from GitHub repo"**
3. Select: `RahulSGosavi/test-interiorr-ai`

### Step 3: Set Environment Variables

1. Go to your project → **"Variables"** tab
2. Add these variables:

```env
SECRET_KEY=your-super-secret-key-change-this
ACCESS_TOKEN_EXPIRE_MINUTES=43200
CORS_ORIGINS=*
PORT=8000
NODE_ENV=production
```

### Step 4: Configure Build

Railway should auto-detect the Dockerfile and build automatically!

### Step 5: Get Your URL

1. Go to **"Settings"** → **"Domains"**
2. Click **"Generate Domain"**
3. Your app will be at: `https://your-app.up.railway.app`

---

## 🐳 Option 3: Docker + Any VPS (DigitalOcean, AWS, etc.)

### Step 1: Build Docker Image Locally

```bash
cd C:\Users\admin\Downloads\Anotation-ai-suit-main
docker build -t annotation-ai-suite .
```

### Step 2: Test Locally with Docker

```bash
docker run -p 8000:8000 \
  -e SECRET_KEY="test-secret-key" \
  -e DATABASE_URL="sqlite:///./app.db" \
  -v ${PWD}/uploads:/app/backend/uploads \
  annotation-ai-suite
```

Visit: http://localhost:8000

### Step 3: Push to Container Registry

#### Option A: Docker Hub
```bash
docker tag annotation-ai-suite yourusername/annotation-ai-suite
docker push yourusername/annotation-ai-suite
```

#### Option B: GitHub Container Registry
```bash
docker tag annotation-ai-suite ghcr.io/rahulsgosavi/annotation-ai-suite
docker push ghcr.io/rahulsgosavi/annotation-ai-suite
```

### Step 4: Deploy to VPS

SSH into your server and run:

```bash
docker pull yourusername/annotation-ai-suite
docker run -d -p 80:8000 \
  --name annotation-ai \
  -e SECRET_KEY="your-secret-key" \
  -e DATABASE_URL="sqlite:///./app.db" \
  -v /opt/uploads:/app/backend/uploads \
  --restart unless-stopped \
  yourusername/annotation-ai-suite
```

---

## 🌐 Option 4: Vercel (Frontend) + Render (Backend)

### Frontend on Vercel

1. Go to https://vercel.com
2. Import from GitHub: `test-interiorr-ai`
3. Configure:
   ```
   Framework Preset: Create React App
   Root Directory: frontend
   Build Command: npm run build
   Output Directory: build
   ```
4. Add Environment Variable:
   ```
   REACT_APP_BACKEND_URL=https://your-backend.onrender.com
   ```

### Backend on Render

Follow "Option 1" above but:
- Set `CORS_ORIGINS=https://your-app.vercel.app`

---

## 🔧 Post-Deployment Configuration

### 1. Update CORS Settings

Once you have your deployment URL, update the backend environment variable:

```env
CORS_ORIGINS=https://your-deployed-app.com
```

### 2. Set Up Database (Production)

For production, use PostgreSQL instead of SQLite:

#### On Render:
1. Create a new **PostgreSQL** database
2. Copy the **Internal Database URL**
3. Add to your web service:
   ```env
   DATABASE_URL=postgresql://user:password@host/database
   ```

#### On Railway:
1. Click **"New"** → **"Database"** → **"PostgreSQL"**
2. Railway will automatically set `DATABASE_URL`

### 3. Custom Domain (Optional)

#### On Render:
1. Go to **"Settings"** → **"Custom Domains"**
2. Add your domain
3. Update your DNS records as shown

#### On Railway:
1. Go to **"Settings"** → **"Domains"**
2. Add custom domain
3. Configure DNS

---

## ✅ Verify Deployment is Working

### 1. Check the Homepage
Visit your deployment URL - should see the login page

### 2. Open Browser DevTools
- Press F12
- Go to **"Network"** tab
- Try logging in
- Check that API calls go to **your deployment URL** (NOT localhost)

Example: `https://your-app.onrender.com/api/auth/login` ✅

### 3. Test All Features
- ✅ Sign up / Login
- ✅ Create project
- ✅ Upload file (PDF)
- ✅ Annotation tools
- ✅ AI pricing assistant
- ✅ Team discussion

---

## 🐛 Common Issues & Solutions

### Issue 1: "ERR_CONNECTION_REFUSED" after deployment

**Cause:** Frontend still trying to connect to localhost

**Solution:**
1. Check that `NODE_ENV=production` is set
2. Rebuild and redeploy
3. Clear browser cache (Ctrl+Shift+Delete)

### Issue 2: CORS Error

**Cause:** Backend blocking requests from your domain

**Solution:**
```env
CORS_ORIGINS=https://your-actual-domain.com
```
Or use `*` for testing (not recommended for production)

### Issue 3: 502 Bad Gateway

**Cause:** Backend not starting properly

**Solution:**
1. Check deployment logs
2. Verify all environment variables are set
3. Check backend port matches (8000 or PORT env var)

### Issue 4: Files not persisting after restart

**Cause:** No persistent storage configured

**Solution:**
- On Render: Add a disk (see Step 5 of Render deployment)
- On Railway: Add a volume mount
- On Docker: Use `-v` volume flag

### Issue 5: Build fails

**Cause:** Usually dependency issues

**Solution:**
1. Check build logs for specific error
2. Common fixes:
   - Delete `node_modules` and rebuild
   - Update `package-lock.json`
   - Check Python version (needs 3.11+)

---

## 🔐 Security Best Practices

### 1. Generate Strong SECRET_KEY
```bash
# Windows PowerShell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})
```

### 2. Use PostgreSQL in Production
SQLite is OK for testing, but use PostgreSQL for real users

### 3. Enable HTTPS
All platforms (Render, Railway, Vercel) provide free SSL automatically!

### 4. Restrict CORS
Set `CORS_ORIGINS` to your actual domain, not `*`

### 5. Regular Backups
- Backup your database
- Backup upload directory

---

## 📊 Monitoring Your App

### Free Monitoring Tools

1. **Uptime Monitoring:**
   - UptimeRobot: https://uptimerobot.com
   - Status page: https://www.statuspage.io

2. **Error Tracking:**
   - Sentry: https://sentry.io (free tier available)
   - LogRocket: https://logrocket.com

3. **Performance:**
   - Google Analytics
   - Vercel Analytics (if using Vercel)

---

## 💰 Cost Estimates

### Free Tier (Perfect for Testing)
- **Render Free:** 750 hours/month, sleeps after 15 min inactivity
- **Railway Free:** $5 credit/month
- **Vercel Free:** Unlimited for personal projects

### Production (Recommended)
- **Render Starter:** $7/month
- **Railway Pro:** $20/month credit
- **PostgreSQL:** $7-15/month

---

## 🎉 Quick Start Checklist

- [ ] Push code to GitHub ✅ (Already done!)
- [ ] Choose deployment platform (Render recommended)
- [ ] Sign up and connect GitHub
- [ ] Set environment variables
- [ ] Deploy!
- [ ] Test the deployed app
- [ ] Set up custom domain (optional)
- [ ] Set up database backup
- [ ] Configure monitoring

---

## 🆘 Need Help?

If you encounter any issues:

1. Check the **build logs** on your deployment platform
2. Check the **runtime logs** for errors
3. Verify all environment variables are set correctly
4. Test locally with Docker first
5. Check the browser console for errors (F12)

---

## 📞 Next Steps

Once deployed, you can:

1. **Share with users:** Give them the deployment URL
2. **Add features:** Continue development and push to GitHub (auto-deploys)
3. **Scale up:** Upgrade to paid tier when you have more users
4. **Add analytics:** Track usage and performance
5. **Custom domain:** Add your own domain name

---

**Happy Deploying! 🚀**

Need help with a specific platform? Just ask!

