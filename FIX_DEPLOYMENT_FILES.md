# 🔧 Fix "Failed to Load PDF" Error After Deployment

## Problem
After deployment, PDFs fail to load with error:
```
Failed to load resource: 404
Failed to load PDF
```

## Root Cause
The application was storing **absolute file paths** in the database (e.g., `/opt/render/project/src/backend/uploads/file.pdf`), which don't work correctly across different deployment environments.

## ✅ Solution Applied
The code now stores **relative paths** (just the filename), making it portable across all environments.

---

## 🚀 How to Fix Your Deployed Instance

### Option 1: Fresh Start (Recommended for Testing)

1. **Redeploy your application** (the new code is already pushed to GitHub)
2. **Delete all existing projects and files**
3. **Upload files again** - they will now be stored correctly

### Option 2: Migrate Existing Data

If you have important data that you don't want to lose:

#### Step 1: Access Your Deployment Shell

**On Render:**
1. Go to your service dashboard
2. Click "Shell" tab
3. Run migration commands

**On Railway:**
1. Go to your project
2. Click on the service
3. Open terminal/shell

#### Step 2: Run Migration Script

```bash
cd backend
python migrate_file_paths.py
```

This will convert all absolute paths to relative paths in your database.

#### Step 3: Verify Upload Directory

Make sure the UPLOAD_DIR environment variable is set correctly:

**For Render:**
```env
UPLOAD_DIR=/opt/render/project/src/backend/uploads
```

**For Railway/Docker:**
```env
UPLOAD_DIR=/app/backend/uploads
```

**For local:**
```env
UPLOAD_DIR=uploads
```

#### Step 4: Restart Your Service

After migration, restart the service for changes to take effect.

---

## 🔍 Debugging Steps

### 1. Check Backend Logs

After deploying, check your backend logs when you try to download a file. You should see:

```
[DEBUG] Attempting to download file: /path/to/uploads/filename.pdf
[DEBUG] UPLOAD_DIR: /path/to/uploads
[DEBUG] File exists: True/False
```

### 2. Check Upload Directory Exists

SSH into your deployment and verify:

```bash
ls -la /opt/render/project/src/backend/uploads/
# or
ls -la /app/backend/uploads/
```

You should see your uploaded files.

### 3. Check Database Records

Connect to your database and check the `files` table:

```sql
SELECT id, name, file_path FROM files;
```

**Old (Wrong):**
```
id | name        | file_path
1  | doc.pdf     | /opt/render/project/src/backend/uploads/abc-123.pdf
```

**New (Correct):**
```
id | name        | file_path
1  | doc.pdf     | abc-123.pdf
```

### 4. Test File Upload

1. Upload a **new PDF file**
2. Check the database - `file_path` should be just a filename (e.g., `abc-123.pdf`)
3. Try to open it in the annotation tool
4. Check backend logs for debug output

---

## 📝 For Local Development

If you're testing locally and get this error:

### 1. Make Sure Backend is Running

```bash
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Check Upload Directory

```bash
# Should exist at: backend/uploads/
ls backend/uploads/
```

### 3. Check Database

```bash
cd backend
python
```

```python
from database import get_db
from models import DBFile

db = next(get_db())
files = db.query(DBFile).all()

for f in files:
    print(f"ID: {f.id}, Name: {f.name}, Path: {f.file_path}")
```

### 4. Run Migration (if needed)

```bash
cd backend
python migrate_file_paths.py
```

---

## 🎯 Configuration Checklist

### Environment Variables

Make sure these are set correctly in your deployment:

```env
# Required
SECRET_KEY=your-secret-key-here
UPLOAD_DIR=/opt/render/project/src/backend/uploads  # Adjust for your platform
PORT=10000  # Or 8000

# Optional but recommended
NODE_ENV=production
CORS_ORIGINS=*  # Or your specific domain
ACCESS_TOKEN_EXPIRE_MINUTES=43200
```

### Persistent Storage (Critical!)

**On Render:**
- Add a **persistent disk** mounted at `/opt/render/project/src/backend/uploads`
- Size: At least 1GB
- This ensures files don't disappear on restart

**On Railway:**
- Add a **volume** at `/app/backend/uploads`
- Files will persist across deployments

**Without persistent storage, uploaded files will be deleted on every restart!**

---

## 🐛 Still Not Working?

### Check These Common Issues:

#### Issue 1: Files Disappear After Restart
**Cause:** No persistent storage configured
**Solution:** Add a persistent disk/volume (see above)

#### Issue 2: Permission Denied
**Cause:** Upload directory not writable
**Solution:** Check directory permissions:
```bash
chmod 755 /opt/render/project/src/backend/uploads
```

#### Issue 3: Wrong Upload Directory
**Cause:** UPLOAD_DIR doesn't match actual location
**Solution:** Update environment variable to match your deployment

#### Issue 4: Old Files Still Don't Work
**Cause:** Database still has old absolute paths
**Solution:** Run the migration script or re-upload files

---

## 📊 Verification Checklist

After applying the fix:

- [ ] Code is pushed to GitHub
- [ ] Application is redeployed
- [ ] Environment variables are set correctly
- [ ] Persistent storage is configured
- [ ] Upload directory exists and is writable
- [ ] Migration script has run (if keeping old data)
- [ ] New file uploads work correctly
- [ ] PDF annotation tool loads files
- [ ] Files persist after restart
- [ ] Backend logs show correct debug info

---

## 🆘 Getting Debug Information

If you still have issues, run this in your deployment shell:

```bash
# Check environment
echo "UPLOAD_DIR: $UPLOAD_DIR"
echo "PORT: $PORT"

# Check upload directory
ls -la $UPLOAD_DIR

# Check if backend can write to upload dir
touch $UPLOAD_DIR/test.txt && rm $UPLOAD_DIR/test.txt && echo "✅ Writable" || echo "❌ Not writable"

# Check database
cd backend
python -c "from database import get_db; from models import DBFile; db = next(get_db()); files = db.query(DBFile).all(); print(f'Files in DB: {len(files)}'); [print(f'  {f.id}: {f.file_path}') for f in files[:5]]"
```

Share the output if you need help debugging!

---

## 🎉 Success!

Once fixed, you should be able to:
1. ✅ Upload PDF files
2. ✅ Open them in the annotation tool
3. ✅ Files persist across restarts
4. ✅ No more 404 errors

---

**Need more help? Check the deployment logs and share them for specific debugging!**

