# Render Deployment Guide with Persistent Storage

## 🎯 Issue Fixed

**Problem**: Projects and files were being deleted after each redeployment because data was stored in the container's filesystem (non-persistent).

**Solution**: Configure a persistent disk in Render to store the SQLite database and uploaded files.

---

## 📋 Deployment Steps

### 1. **Create New Web Service on Render**

1. Go to [render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository

### 2. **Configure Service Settings**

| Setting | Value |
|---------|-------|
| **Name** | `annotation-ai-app` (or your choice) |
| **Environment** | `Docker` |
| **Branch** | `main` |
| **Plan** | `Free` (or higher for better performance) |

### 3. **⚠️ IMPORTANT: Add Persistent Disk**

This is **critical** to prevent data loss:

1. In the service settings, scroll to **"Disks"**
2. Click **"Add Disk"**
3. Configure:
   - **Name**: `app-data`
   - **Mount Path**: `/app/backend`
   - **Size**: `1 GB` (Free plan allows up to 1GB)
4. Click **"Create Disk"**

### 4. **Configure Environment Variables**

Add these in the **"Environment"** tab:

| Variable | Value | Notes |
|----------|-------|-------|
| `SECRET_KEY` | *Auto-generated* | Click "Generate" button |
| `DATABASE_URL` | *(leave empty)* | Will use SQLite on persistent disk |
| `UPLOAD_DIR` | `/app/backend/uploads` | Uploads stored on persistent disk |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `43200` | Token expires in 30 days |
| `NODE_ENV` | `production` | |

**Optional AI Keys** (for Pricing AI feature):
| Variable | Value |
|----------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `OPENAI_API_KEY` | Your OpenAI API key |

### 5. **Deploy**

1. Click **"Create Web Service"**
2. Wait for the build to complete (~5-10 minutes first time)
3. Check the **"Logs"** tab for:
   ```
   ✅ Using SQLite database at sqlite:////app/backend/local.db
   ✅ Successfully connected to DATABASE_URL
   ```

### 6. **Verify Persistent Storage**

After deployment:
1. Create a test project and upload a file
2. Go to Render → **"Manual Deploy"** → **"Deploy latest commit"**
3. After redeployment, check if your project still exists
4. ✅ If yes, persistent storage is working!

---

## 🔧 Alternative: PostgreSQL Database

For production use, consider PostgreSQL for better performance:

### Option 1: Render PostgreSQL

1. Create a PostgreSQL database on Render (Free tier available)
2. Copy the **Internal Database URL**
3. Set as `DATABASE_URL` environment variable

### Option 2: Supabase

1. Create free PostgreSQL database at [supabase.com](https://supabase.com)
2. Get connection string from Settings → Database
3. Format: `postgresql://postgres:[password]@[host]:5432/postgres`
4. Set as `DATABASE_URL` environment variable

**Note**: The app auto-converts `postgres://` to `postgresql://` for compatibility.

---

## 📊 Health Check

The app includes a health check endpoint:

**URL**: `https://your-app.onrender.com/api/health`

**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "upload_dir": "/app/backend/uploads",
  "upload_dir_exists": true
}
```

Render automatically uses this to monitor your app.

---

## 🐛 Troubleshooting

### Projects Disappear After Deployment

**Cause**: Persistent disk not configured or wrong mount path.

**Fix**:
1. Check **"Disks"** tab in Render
2. Verify disk is mounted to `/app/backend`
3. Redeploy after adding disk

### "Network is unreachable" Database Error

**Cause**: PostgreSQL connection failed (e.g., Supabase).

**Fix**:
- App automatically falls back to SQLite
- Check logs for `✅ Using SQLite database`
- For PostgreSQL, verify connection string and network access

### Upload Folder Not Found

**Cause**: `UPLOAD_DIR` environment variable incorrect.

**Fix**:
- Set `UPLOAD_DIR=/app/backend/uploads`
- Ensure it's inside the mounted disk path

---

## 💾 Disk Space Management

**Free Plan**: 1GB disk
- SQLite database: ~10-50MB for typical use
- Uploads: Remaining space (~950MB)

**Monitor Usage**:
- Check Render dashboard → Service → Disks
- Clean old files periodically if needed

---

## 🚀 Performance Tips

1. **Upgrade Plan**: Free tier has limited resources
2. **Use PostgreSQL**: Better for concurrent users
3. **CDN for Uploads**: Store large files on S3/Cloudflare R2
4. **Database Backups**: Download SQLite file periodically from disk

---

## ✅ Success Checklist

- [ ] Persistent disk added and mounted to `/app/backend`
- [ ] Environment variables configured
- [ ] Health check returns `"status": "healthy"`
- [ ] Test project survives redeployment
- [ ] Files upload and download correctly
- [ ] Mobile navigation displays properly (no cutoff)

---

## 📱 Mobile Navigation Fix

The app now properly handles mobile notches and safe areas:

**CSS Variables**:
```css
--safe-area-inset-top
--safe-area-inset-bottom
--safe-area-inset-left
--safe-area-inset-right
```

**Applied to**:
- Annotation page header
- All page containers

**Result**: Navigation bars no longer hidden on iPhone X+, Android punch-hole displays

---

## 📞 Support

If you encounter issues:
1. Check Render logs for errors
2. Verify disk is properly mounted
3. Test health endpoint
4. Ensure environment variables are set correctly

