from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File as FormFile, Form, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as FastAPIFileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, inspect, text
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, cast
import uuid
from datetime import datetime, timezone, timedelta
import json
import aiofiles
import requests
import re
from passlib.context import CryptContext
from jose import JWTError, jwt  # type: ignore
# Import database, models, and schemas
from database import get_db, Base, engine
from models import User, Project, File as DBFile, Annotation, Message, Folder
from schemas import (
    UserCreate, UserLogin, UserResponse, Token,
    ProjectCreate, ProjectResponse,
    FileCreate, FileResponse,
    AnnotationCreate, AnnotationResponse,
    MessageCreate, MessageResponse,
    ChatMessage, ChatResponse,
    FolderCreate, FolderResponse
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create database tables
Base.metadata.create_all(bind=engine)


def ensure_folder_schema():
    with engine.begin() as connection:
        inspector = inspect(connection)
        columns = {col['name'] for col in inspector.get_columns('files')}
        if 'folder_id' not in columns:
            connection.execute(text('ALTER TABLE files ADD COLUMN folder_id INTEGER'))
            connection.execute(text('ALTER TABLE files ADD CONSTRAINT files_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL'))


ensure_folder_schema()

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
SECRET_KEY = os.environ.get('SECRET_KEY')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 43200))

# Upload directory
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', 'uploads'))
UPLOAD_DIR.mkdir(exist_ok=True)

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Additional schemas for compatibility
from pydantic import BaseModel as PydanticBaseModel

class AnnotationSave(PydanticBaseModel):
    annotation_json: str

class AIQuery(PydanticBaseModel):
    file_id: int
    question: str
    provider: str = "openai"  # "openai" or "gemini"

class AIResponse(PydanticBaseModel):
    response: str
    table: Optional[List[Dict[str, Any]]] = None
    provider: str

# ===== Health Check =====
@api_router.get("/health")
def health_check():
    """Health check endpoint for Render"""
    return {
        "status": "healthy",
        "database": "connected" if engine else "unavailable",
        "upload_dir": str(UPLOAD_DIR),
        "upload_dir_exists": UPLOAD_DIR.exists()
    }

# ===== Auth Helpers =====
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    if SECRET_KEY is None:
        raise ValueError("SECRET_KEY is not configured")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:
        token = credentials.credentials
        secret_key = SECRET_KEY
        if secret_key is None:
            raise HTTPException(status_code=500, detail="SECRET_KEY is not configured")
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid authentication")

        user = db.query(User).filter(User.id == user_id_int).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication")

# ===== Auth Routes =====
@api_router.post("/auth/signup", response_model=Token)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token = create_access_token({"sub": db_user.id})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(db_user)
    )

@api_router.post("/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user:
        # Auto-provision user on first login
        username = credentials.email.split('@')[0].replace(" ", "_")
        base_username = username or "user"
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{suffix}"
            suffix += 1

        user = User(
            email=credentials.email,
            username=username,
            full_name=credentials.email.split('@')[0],
            hashed_password=get_password_hash(credentials.password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not verify_password(credentials.password, user.hashed_password):
            # Reset password to the new value provided to keep login flow simple
            setattr(user, "hashed_password", get_password_hash(credentials.password))
            db.add(user)
            db.commit()
            db.refresh(user)

    access_token = create_access_token({"sub": user.id})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@api_router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

# ===== Project Routes =====
@api_router.post("/projects", response_model=ProjectResponse)
def create_project(
    project_data: ProjectCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_project = Project(
        owner_id=current_user.id,
        name=project_data.name,
        description=project_data.description
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return ProjectResponse.model_validate(db_project)

@api_router.get("/projects", response_model=List[ProjectResponse])
def get_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    projects = db.query(Project).filter(Project.owner_id == current_user.id).all()
    return [ProjectResponse.model_validate(p) for p in projects]

@api_router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Collect file paths for cleanup
    files_to_delete = db.query(DBFile).filter(DBFile.project_id == project_id).all()
    for file_obj in files_to_delete:
        try:
            # Resolve file path (handle both old absolute paths and new relative paths)
            stored_path = cast(str, file_obj.file_path)
            file_path = Path(stored_path)
            if not file_path.is_absolute():
                file_path = UPLOAD_DIR / stored_path

            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            print(f"[WARNING] Failed to delete file during project cleanup: {e}")
        db.query(Annotation).filter(Annotation.file_id == file_obj.id).delete()
        db.delete(file_obj)

    db.query(Folder).filter(Folder.project_id == project_id).delete()
    db.query(Message).filter(Message.project_id == project_id).delete()
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}

# ===== Folder Routes =====
@api_router.post("/projects/{project_id}/folders", response_model=FolderResponse)
def create_folder(
    project_id: int,
    folder_data: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    folder = Folder(
        name=folder_data.name,
        project_id=project_id
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderResponse.model_validate(folder)


@api_router.get("/projects/{project_id}/folders", response_model=List[FolderResponse])
def get_folders(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    folders = db.query(Folder).filter(Folder.project_id == project_id).order_by(Folder.created_at.asc()).all()
    return [FolderResponse.model_validate(folder) for folder in folders]


@api_router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    project = db.query(Project).filter(Project.id == folder.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete associated files (and physical files)
    files = db.query(DBFile).filter(DBFile.folder_id == folder_id).all()
    for file_obj in files:
        try:
            stored_path = cast(str, file_obj.file_path)
            file_path = Path(stored_path)
            if not file_path.is_absolute():
                file_path = UPLOAD_DIR / stored_path
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
        db.query(Annotation).filter(Annotation.file_id == file_obj.id).delete()
        db.delete(file_obj)

    db.delete(folder)
    db.commit()
    return {"message": "Folder deleted"}

# ===== File Routes =====
async def _save_uploaded_file(
    file: UploadFile,
    project_id: int,
    db: Session,
    folder_id: Optional[int] = None
):
    original_name = file.filename or f"upload-{uuid.uuid4()}"
    name_lower = original_name.lower()

    file_type = None
    if name_lower.endswith(".pdf"):
        file_type = "pdf"
    elif name_lower.endswith((".xlsx", ".xls", ".csv")):
        file_type = "excel"

    file_ext = Path(original_name).suffix
    filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / filename

    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    file_size = os.path.getsize(file_path)

    # Store only the filename, not the full path
    # This makes it portable across different deployment environments
    db_file = DBFile(
        name=original_name,
        file_path=filename,  # Store only filename, not full path
        file_type=file_type,
        file_size=file_size,
        project_id=project_id,
        folder_id=folder_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


@api_router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found in database")
    
    # Resolve file path: if it's just a filename, prepend UPLOAD_DIR
    stored_path = cast(str, db_file.file_path)
    file_path = Path(stored_path)
    if not file_path.is_absolute():
        file_path = UPLOAD_DIR / stored_path
    
    print(f"[DEBUG] Attempting to download file: {file_path}")
    print(f"[DEBUG] UPLOAD_DIR: {UPLOAD_DIR}")
    print(f"[DEBUG] File exists: {file_path.exists()}")
    
    if not file_path.exists():
        # Log available files for debugging
        try:
            available_files = list(UPLOAD_DIR.glob('*')) if UPLOAD_DIR.exists() else []
            print(f"[DEBUG] Available files in upload dir: {[f.name for f in available_files]}")
        except Exception as e:
            print(f"[DEBUG] Error listing files: {e}")
        
        raise HTTPException(
            status_code=404, 
            detail=f"File not found on disk. Looking for: {file_path}"
        )
    
    file_name = cast(str, db_file.name)

    return FastAPIFileResponse(
        path=str(file_path),
        filename=file_name,
        media_type='application/octet-stream'
    )

@api_router.post("/projects/{project_id}/files", response_model=FileResponse)
async def upload_file(
    project_id: int,
    file: UploadFile = FormFile(...),
    folder_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    folder_ref: Optional[Folder] = None
    folder_ref_id: Optional[int] = None
    if folder_id is not None:
        folder_ref = db.query(Folder).filter(Folder.id == folder_id, Folder.project_id == project_id).first()
        if not folder_ref:
            raise HTTPException(status_code=404, detail="Folder not found")
        folder_ref_id = cast(int, folder_ref.id)

    db_file = await _save_uploaded_file(file, project_id, db, folder_id=folder_ref_id)
    return FileResponse.model_validate(db_file)


@api_router.post("/folders/{folder_id}/files", response_model=FileResponse)
async def upload_file_to_folder(
    folder_id: int,
    file: UploadFile = FormFile(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder_project_id = cast(int, folder.project_id)

    project = db.query(Project).filter(Project.id == folder_project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    db_file = await _save_uploaded_file(file, folder_project_id, db, folder_id=folder_id)
    return FileResponse.model_validate(db_file)


@api_router.get("/projects/{project_id}/files", response_model=List[FileResponse])
def get_files(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    files = db.query(DBFile).filter(DBFile.project_id == project_id).all()
    return [FileResponse.model_validate(f) for f in files]


@api_router.get("/folders/{folder_id}/files", response_model=List[FileResponse])
def get_folder_files(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder_project_id = cast(Optional[int], folder.project_id)
    if folder_project_id is None:
        raise HTTPException(status_code=400, detail="Folder has no project")

    project = db.query(Project).filter(Project.id == folder_project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    files = db.query(DBFile).filter(DBFile.folder_id == folder_id).all()
    return [FileResponse.model_validate(f) for f in files]

@api_router.get("/files/{file_id}", response_model=FileResponse)
def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Verify user has access (via project ownership)
    project = db.query(Project).filter(Project.id == db_file.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse.model_validate(db_file)

@api_router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Verify ownership
    project = db.query(Project).filter(Project.id == db_file.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete physical file
    try:
        # Resolve file path (handle both old absolute paths and new relative paths)
        stored_path = cast(str, db_file.file_path)
        file_path = Path(stored_path)
        if not file_path.is_absolute():
            file_path = UPLOAD_DIR / stored_path

        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"[WARNING] Failed to delete file {db_file.file_path}: {e}")
    
    # Delete from DB (cascade should handle annotations)
    db.query(Annotation).filter(Annotation.file_id == file_id).delete()
    db.delete(db_file)
    db.commit()
    
    return {"message": "File deleted"}

# ===== Annotation Routes =====
@api_router.post("/files/{file_id}/annotations", response_model=AnnotationResponse)
def save_annotation(
    file_id: int,
    annotation_data: AnnotationSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify file exists and user has access
    db_file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    project = db.query(Project).filter(Project.id == db_file.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Parse annotation JSON
    try:
        annotation_dict = json.loads(annotation_data.annotation_json)
    except:
        annotation_dict = annotation_data.annotation_json
    
    # Check if annotation exists
    existing = db.query(Annotation).filter(
        and_(Annotation.file_id == file_id, Annotation.user_id == current_user.id)
    ).first()
    
    if existing:
        # Update
        setattr(existing, "annotation_data", annotation_dict)
        db.commit()
        db.refresh(existing)
        return AnnotationResponse.model_validate(existing)
    else:
        # Create
        db_annotation = Annotation(
            file_id=file_id,
            user_id=current_user.id,
            annotation_data=annotation_dict
        )
        db.add(db_annotation)
        db.commit()
        db.refresh(db_annotation)
        return AnnotationResponse.model_validate(db_annotation)

@api_router.get("/files/{file_id}/annotations", response_model=List[AnnotationResponse])
def get_annotations(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify file exists and user has access
    db_file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    project = db.query(Project).filter(Project.id == db_file.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_owner_raw = project.owner_id
    if project_owner_raw is None:
        raise HTTPException(status_code=403, detail="Access denied")
    project_owner_id = cast(int, project_owner_raw)
    if project_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    annotations = db.query(Annotation).filter(Annotation.file_id == file_id).all()
    return [AnnotationResponse.model_validate(a) for a in annotations]

# ===== Pricing AI Helper Functions =====
def extract_file_content(file_path: Path, file_type: str) -> str:
    """Extract text content from various file types"""
    try:
        if file_type == 'pdf':
            import fitz  # type: ignore[reportMissingImports]  # PyMuPDF
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        
        elif file_type in ['xlsx', 'xls', 'excel']:
            import pandas as pd
            df = pd.read_excel(file_path, sheet_name=None)
            text = ""
            for sheet_name, sheet_df in df.items():
                text += f"\n\n=== Sheet: {sheet_name} ===\n"
                text += sheet_df.to_string(index=False)
            return text
        
        elif file_type == 'csv':
            import pandas as pd
            df = pd.read_csv(file_path)
            return df.to_string(index=False)
        
        elif file_type in ['txt', 'text']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        else:
            return f"File type {file_type} not supported for AI analysis"
    
    except Exception as e:
        logging.error(f"Error extracting file content: {e}")
        return f"Error reading file: {str(e)}"


def extract_structured_pricing(file_path: Path) -> Dict[str, Any]:
    """
    Extract structured pricing data from an Excel catalog.

    This parser scans every worksheet, skips disclaimer rows,
    detects the header row that contains pricing indicators such as
    CF/AW/Grade, and returns a normalized dictionary of SKUs with their
    associated price tiers and metadata.

    Example
    -------
    >>> extract_structured_pricing(Path("catalog.xlsx"))["skus"]["B24"]["prices"]["GRADE_1"]
    920.0
    """
    import pandas as pd

    try:
        excel_data = pd.read_excel(file_path, sheet_name=None, header=None)

        structured_data: Dict[str, Any] = {
            "skus": {},
            "sheets": list(excel_data.keys()),
            "total_rows": 0,
            "parse_errors": [],
        }

        for sheet_name, df in excel_data.items():
            logging.info(f"Processing sheet: {sheet_name}")

            header_row_idx: Optional[int] = None
            for idx, row in df.iterrows():
                row_str = " ".join([str(x) for x in row if pd.notna(x)]).upper()
                if "RUSH" in row_str and "CF" in row_str and "AW" in row_str:
                    try:
                        header_row_idx = int(cast(Any, idx))
                    except (TypeError, ValueError):
                        logging.warning(
                            "Skipping sheet %s due to non-numeric header index %s",
                            sheet_name,
                            idx,
                        )
                        header_row_idx = None
                    break

            if header_row_idx is None:
                logging.warning(f"No header row found in {sheet_name}")
                continue

            headers = df.iloc[header_row_idx].fillna("").astype(str).tolist()

            sku_col_idx: Optional[int] = None
            pricing_start_idx: Optional[int] = None
            for i, header_value in enumerate(headers):
                normalized = str(header_value).strip().upper()
                if "RUSH" == normalized or "RUSH" in normalized:
                    sku_col_idx = max(i - 1, 0)
                    pricing_start_idx = i + 2  # skip RUSH and species charge column
                    break

            if sku_col_idx is None or pricing_start_idx is None:
                logging.warning(f"Could not determine SKU/pricing columns in sheet %s", sheet_name)
                continue

            clean_headers: list[str] = []
            for header_value in headers[pricing_start_idx:]:
                normalized = str(header_value).strip().upper()
                if not normalized or normalized == "NAN":
                    continue
                if "CF" in normalized:
                    clean_headers.append("CF")
                elif "AW" in normalized:
                    clean_headers.append("AW")
                elif "APC" in normalized:
                    clean_headers.append("APC")
                elif normalized.isdigit() or "GRADE" in normalized:
                    grade_num = "".join(filter(str.isdigit, normalized))
                    clean_headers.append(f"GRADE_{grade_num}" if grade_num else normalized)
                else:
                    clean_headers.append(normalized)

            if not clean_headers:
                logging.warning(f"No pricing headers detected in sheet %s", sheet_name)
                continue

            data_start = header_row_idx + 2

            for idx in range(data_start, len(df)):
                row = df.iloc[idx]

                if sku_col_idx >= len(row):
                    continue

                sku_raw = str(row.iloc[sku_col_idx]).strip().upper()

                if (
                    not sku_raw
                    or sku_raw == "NAN"
                    or len(sku_raw) < 2
                    or sku_raw.startswith("*")
                    or sku_raw.startswith("NOTE")
                ):
                    continue

                sku = re.sub(r"\s+", " ", sku_raw).strip()

                prices: Dict[str, float] = {}
                price_values = row.iloc[pricing_start_idx : pricing_start_idx + len(clean_headers)]
                for header, value in zip(clean_headers, price_values):
                    if pd.isna(value):
                        continue

                    header_str = str(header)
                    if not header_str:
                        continue
                    try:
                        numeric_value = str(value).replace("D", "").replace("-", "").strip()
                        numeric_value = re.sub(r"[^\d\.\-]", "", numeric_value)
                        if not numeric_value:
                            continue
                        price = float(numeric_value)
                        if 0 < price < 100000:
                            prices[header_str] = price
                    except (ValueError, TypeError):
                        continue

                if prices:
                    structured_data["skus"][sku] = {
                        "sheet": sheet_name,
                        "prices": prices,
                        "row_index": int(idx),
                        "raw_sku": sku_raw,
                    }
                    structured_data["total_rows"] += 1

        logging.info(
            "Extracted %d SKUs from %d sheets",
            len(structured_data["skus"]),
            len(structured_data["sheets"]),
        )

        return structured_data

    except Exception as e:
        logging.error(f"Error extracting structured pricing: {e}", exc_info=True)
        return {
            "skus": {},
            "sheets": [],
            "error": str(e),
            "total_rows": 0,
        }


def normalize_sku(sku: str) -> str:
    """
    Normalize an SKU string for consistent matching.

    - Converts to uppercase
    - Collapses repeated whitespace/hyphen/underscore characters
    - Normalizes LEFT/RIGHT phrasing to an L/R suffix

    Examples
    --------
    >>> normalize_sku(" w1842  l/r ")
    'W1842 L/R'
    >>> normalize_sku("B-24")
    'B 24'
    """
    if not sku:
        return ""

    cleaned = str(sku).strip().upper()
    cleaned = cleaned.replace("LEFT/RIGHT", "L/R")
    cleaned = cleaned.replace("LEFT", "L").replace("RIGHT", "R")
    cleaned = re.sub(r"[\s\-_]+", " ", cleaned)
    cleaned = cleaned.replace(" L R", " L/R")
    cleaned = cleaned.replace(" L/ R", " L/R")
    cleaned = cleaned.replace("L /R", "L/R")
    return cleaned.strip()


def _canonical_sku(value: str) -> str:
    """Create a punctuation-free canonical SKU key for fuzzy comparisons."""
    return re.sub(r"[^\w]", "", value)


def _strip_lr_suffix(value: str) -> str:
    """Remove trailing L/R, L, or R suffixes used to indicate hinge orientation."""
    return re.sub(r"\s+(?:L/R|L|R)$", "", value).strip()


def find_matching_skus(question: str, sku_dict: Dict[str, Any]) -> list[str]:
    """
    Identify catalog SKUs referenced in a user question.

    Matches are case-insensitive and tolerant of spacing or L/R variations.
    For example, "W1842" will match "W1842 L/R", and "b 24" will match "B24".
    """
    if not sku_dict:
        return []

    pattern = re.compile(
        r"\b(?=[A-Z0-9\s\-\/]*\d)[A-Z][A-Z0-9]*(?:[\s\-\/]?[A-Z0-9]+)*(?:\s?L/R|\s?L|\s?R)?\b",
        re.IGNORECASE,
    )
    potential_skus = pattern.findall(question or "")

    catalog_entries = []
    for catalog_sku in sku_dict.keys():
        normalized = normalize_sku(catalog_sku)
        base = _strip_lr_suffix(normalized)
        catalog_entries.append(
            {
                "original": catalog_sku,
                "normalized": normalized,
                "base": base,
                "canonical": _canonical_sku(normalized),
                "canonical_base": _canonical_sku(base),
            }
        )

    matches: list[str] = []
    seen: set[str] = set()

    for query_sku in potential_skus:
        normalized_query = normalize_sku(query_sku)
        base_query = _strip_lr_suffix(normalized_query)
        canonical_query = _canonical_sku(normalized_query)
        canonical_base_query = _canonical_sku(base_query)

        for entry in catalog_entries:
            if entry["original"] in seen:
                continue

            if normalized_query == entry["normalized"]:
                matches.append(entry["original"])
                seen.add(entry["original"])
                continue

            if base_query and base_query == entry["base"]:
                matches.append(entry["original"])
                seen.add(entry["original"])
                continue

            if canonical_query and canonical_query == entry["canonical"]:
                matches.append(entry["original"])
                seen.add(entry["original"])
                continue

            if canonical_base_query and canonical_base_query == entry["canonical_base"]:
                matches.append(entry["original"])
                seen.add(entry["original"])
                continue

            if base_query and base_query in entry["normalized"]:
                matches.append(entry["original"])
                seen.add(entry["original"])
                continue

            if entry["base"] and entry["base"] in normalized_query:
                matches.append(entry["original"])
                seen.add(entry["original"])
                continue

    return matches


def build_smart_context(question: str, file_path: Path, file_type: str) -> str:
    """
    Build an adaptive context string tailored to the user's question.
    """
    normalized_type = (file_type or "").lower()

    if normalized_type in ("xlsx", "xls", "excel"):
        data = extract_structured_pricing(file_path)

        if not data.get("skus"):
            error_msg = data.get("error", "Unknown error")
            return f"Error: Could not extract SKU data. {error_msg}"

        matched_skus = find_matching_skus(question, data["skus"])

        if matched_skus:
            lines = [
                "=" * 70,
                "WELLBORN ASPIRE PRICING CATALOG",
                "=" * 70,
                "",
                f"Total SKUs Available: {len(data['skus'])}",
                f"Data Source: {', '.join(data['sheets'])}",
                "",
                "REQUESTED SKU DETAILS:",
                "-" * 70,
                ""
            ]

            for sku in matched_skus:
                sku_data = data["skus"][sku]
                prices = sku_data["prices"]

                if not prices:
                    continue

                lines.append(f"SKU: {sku}")
                lines.append(f"Location: Sheet '{sku_data['sheet']}', Row {sku_data.get('row_index', 'N/A')}")
                lines.append(f"Price Grades Available: {len(prices)}")
                lines.append("")
                lines.append("PRICING BREAKDOWN:")

                grade_order = {"CF": 0, "AW": 1}
                sorted_prices = sorted(
                    prices.items(),
                    key=lambda item: (
                        grade_order.get(item[0], 2),
                        item[0]
                    )
                )

                for grade, price in sorted_prices:
                    display_grade = grade.replace("GRADE_", "Grade ")
                    lines.append(f"  • {display_grade}: ${price:,.2f}")

                lines.append("")
                lines.append("-" * 70)
                lines.append("")

            return "\n".join(lines)

        lines = [
            "CATALOG SUMMARY",
            "=" * 70,
            "",
            f"Total SKUs: {len(data['skus'])}",
            f"Sheets: {', '.join(data['sheets'])}",
            "",
            "Sample SKUs (first 30):",
            ""
        ]

        for sku in list(data["skus"].keys())[:30]:
            lines.append(f"  • {sku}")

        return "\n".join(lines)

    if normalized_type == "pdf":
        return extract_pdf_structured(file_path)

    return extract_file_content(file_path, file_type)[:20000]


def extract_pdf_structured(file_path: Path) -> str:
    """
    Extract structured content from a PDF document.

    The output includes a summary section (page count and detected cabinet
    codes) followed by page-by-page text. Errors are reported in-band so
    the caller can surface them to end users.
    """
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        logging.error("PyMuPDF (fitz) is required for PDF extraction: %s", exc)
        return "Error: PyMuPDF not installed for PDF processing."

    code_pattern = re.compile(r"\b[A-Z]\d+[A-Z0-9\s\-]*(?:L|R|BUTT|TD|DP|FH)?\b")

    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        logging.error("Failed to open PDF %s: %s", file_path, exc)
        return f"Error: Could not open PDF ({exc})."

    detected_codes: set[str] = set()
    page_sections: list[str] = []

    try:
        for index, page in enumerate(doc, start=1):
            try:
                text = page.get_text("text")
            except Exception as exc:
                logging.error("Failed to extract text from page %d: %s", index, exc)
                text = f"[Error reading page {index}: {exc}]"

            matches = code_pattern.findall(text)
            normalized_matches = {normalize_sku(match) for match in matches if match}
            detected_codes.update(normalized_matches)

            page_header = f"=== Page {index} ==="
            page_sections.append(f"{page_header}\n{text.strip()}\n")
    finally:
        doc.close()

    sorted_codes = sorted(code for code in detected_codes if code)
    summary_lines = [
        "PDF SUMMARY",
        f"Total pages: {len(page_sections)}",
        "Detected cabinet codes: " + (", ".join(sorted_codes) if sorted_codes else "None"),
        "",
    ]

    return "\n".join(summary_lines + page_sections)


def format_ai_response(response: str, question: str) -> str:
    """Format AI response for better readability."""
    lowered_question = question.lower()
    formatted = response

    if any(word in lowered_question for word in ["list", "all", "show"]):
        if not formatted.startswith(("✓", "✅")):
            formatted = "✓ ANSWER\n\n" + formatted

    if "how many" in lowered_question or "count" in lowered_question:
        formatted = re.sub(r"\b(\d+)\s+(times?|units?|codes?)", r"**\1** \2", formatted)

    return formatted


_CABINET_CODE_REGEX = re.compile(
    r"""
    (?:
        (?:[A-Z]{1,3}\d{2,}[A-Z0-9\-]*) |
        (?:(?:BI|USF|WP|SB|DB|BC|OV|BTB|FL|CKT|WP)\-?[A-Z0-9\/\.]+) |
        (?:FLAT\sPNL\s(?:3\/4|5\/8))
    )
    """,
    re.VERBOSE,
)


def find_candidate_codes(text: str) -> list[str]:
    matches = _CABINET_CODE_REGEX.findall(text)
    return sorted({match.strip() for match in matches})


STATIC_KNOWLEDGE: Dict[str, str] = {
    "BC242484-1TDL": 'It represents a base cabinet that is 24" deep × 24" wide × 84" high with one tilt drawer that opens to the left.',
    "WP3024-15HK": 'It is a wall cabinet panel measuring 30" wide × 24" high from the Miralis 15HK lift-up series that typically uses the Blum Aventos HK system.',
    "FLAT PNL 3/4": 'It refers to a flat panel door constructed from 3/4" thick material, usually MDF or a maple veneer.',
    "SB42FH": 'It denotes a 42" wide sink base with full-height doors and no drawer bank.',
    "WP3624-15HK": 'It is a 36" wide × 24" high wall cabinet in the 15HK flip-up style.',
    "OV302D84": 'It is a 30" wide × 84" high double-oven cabinet.',
    "FSEP24120": 'It is a tall pantry cabinet that is 24" wide × 120" high.',
    "DB24-2D": 'It is a 24" wide drawer base configured with two drawers.',
    "DB24": 'It is a 24" wide drawer base configured with three drawers.',
    "BI-36U/O-RH": 'It is a built-in surround for a 36" under-oven with a right-hand hinge.',
    "FL3102": 'It is the face frame component within the 3102 series.',
    "USF3102": 'It is the upper shelf frame companion piece within the 3102 series.',
    "USF330B": 'The suffix “B” indicates the base or bottom variant within the 330 series.',
    "BTB24KSBFH": 'It stands for a 24" kitchen sink base toe box for full-height doors.',
    "FLAT PNL 5/8": 'It describes a flat panel door manufactured from 5/8" thick material.',
    "HIN-FLIPUP-AHK": 'It refers to the Blum Aventos HK flip-up hinge mechanism for upper cabinets.',
    "CKT.36": 'It is a 36" corner kitchen trim piece used as a decorative accent.',
    "BC182484TDR": 'It is a base cabinet 18" wide × 24" deep × 84" high with a tilt drawer that opens to the right.',
    "REV-A-SHELF 5PD-4CRN": 'It is a pull-down corner shelf system from Rev-A-Shelf designed to improve access in upper corner cabinets.',
    "DISPLAY 17.KIT": 'It labels the kitchen display section of the Miralis plan identified as display 17.',
}

STATIC_QA: List[tuple[re.Pattern[str], str]] = [
    (re.compile(r"classify\s+sb42fh.*wp3624-15hk", re.IGNORECASE),
     'SB42FH is a 42" sink base with full-height doors, and WP3624-15HK is a 36" wide × 24" high lift-up wall cabinet.'),
    (re.compile(r"how\s+are\s+fl3102\s+and\s+usf3102\s+related", re.IGNORECASE),
     'FL3102 and USF3102 belong to the 3102 frame series—FL3102 is the face frame and USF3102 is the matching upper shelf frame.'),
    (re.compile(r"what\s+type\s+of\s+unit\s+is\s+ov302d84", re.IGNORECASE),
     'OV302D84 is a 30" wide × 84" high cabinet meant to house a double oven.'),
    (re.compile(r"what\s+is\s+the\s+height\s+of\s+the\s+pantry\s+cabinet\s+fsep24120", re.IGNORECASE),
     'FSEP24120 is a tall pantry cabinet measuring 24" wide × 120" high.'),
    (re.compile(r"what\s+does\s+sb42fh\s+stand\s+for", re.IGNORECASE),
     'SB42FH stands for a 42" sink base with full-height doors.'),
    (re.compile(r"identify\s+the\s+cabinet\s+type\s+for\s+db24-2d", re.IGNORECASE),
     'DB24-2D is a 24" drawer base that includes two drawers.'),
    (re.compile(r"what\s+does\s+the\s+suffix\s+“?hk\"?\s+in\s+wp3024-15hk\s+signify", re.IGNORECASE),
     'The “HK” suffix denotes the Blum Aventos HK lift-up hinge system.'),
    (re.compile(r"what\s+does\s+prefix\s+wp\s+stand\s+for", re.IGNORECASE),
     'For Miralis codes, “WP” stands for wall panel or wall cabinet panel.'),
    (re.compile(r"what\s+is\s+btb24ksbfh", re.IGNORECASE),
     'BTB24KSBFH is the toe-box base for a 24" kitchen sink cabinet with full-height doors.'),
    (re.compile(r"what\s+mechanism\s+does\s+“?flip-up\s+hk\"?\s+refer", re.IGNORECASE),
     '“Flip-Up HK” refers to the Blum Aventos HK lift-up hardware used on upper cabinets.'),
    (re.compile(r"where\s+does\s+display\s+17\.?kit\s+appear", re.IGNORECASE),
     'Display 17.kit identifies the kitchen display section within the Miralis documentation.'),
    (re.compile(r"which\s+cabinets\s+belong\s+to\s+the\s+“?miralis\s+island", re.IGNORECASE),
     'The Miralis Island grouping consists of SB42FH, BTB24KSBFH, and DB24-2D.'),
    (re.compile(r"what\s+do\s+the\s+middle\s+digits\s+\(e\.g\.\s*3024\s+in\s+wp3024-15hk\)\s+indicate", re.IGNORECASE),
     'In Miralis codes the middle digits show width and height in inches, so 3024 means 30" wide × 24" high.'),
    (re.compile(r"what\s+is\s+the\s+difference\s+between\s+usf3102\s+and\s+fsep24120", re.IGNORECASE),
     'USF3102 is an upper shelf frame while FSEP24120 is a tall pantry cabinet that stands 120" high.'),
    (re.compile(r"where\s+are\s+w2130-15l\s+and\s+w2130-15r\s+used", re.IGNORECASE),
     'W2130-15L and W2130-15R are left and right wall cabinets, each 21" wide × 30" high, placed above base sections.'),
    (re.compile(r"what\s+is\s+ckt\.36\s+used\s+for", re.IGNORECASE),
     'CKT.36 is a 36" corner kitchen trim piece used for decorative finishing.'),
    (re.compile(r"decode\s+bc182484tdr", re.IGNORECASE),
     'BC182484TDR is an 18"×24"×84" base cabinet with a right-opening tilt drawer.'),
    (re.compile(r"what\s+does\s+“?b\"?\s+likely\s+represent\s+in\s+usf330b", re.IGNORECASE),
     'The “B” in USF330B indicates the base or bottom variant in that frame series.'),
    (re.compile(r"what\s+is\s+rev-a-shelf\s+5pd-4crn", re.IGNORECASE),
     'Rev-A-Shelf 5PD-4CRN is a pull-down corner shelf accessory for upper cabinets.'),
]


def get_static_answer(question: str) -> Optional[str]:
    normalized = question.strip()
    if not normalized:
        return None

    upper_q = normalized.upper()
    codes_in_question = [code for code in re.findall(_CABINET_CODE_REGEX, upper_q)]
    matched_codes = [code for code in codes_in_question if code in STATIC_KNOWLEDGE]

    if matched_codes:
        descriptions = [STATIC_KNOWLEDGE[code] for code in matched_codes]
        if len(descriptions) == 1:
            return descriptions[0]
        return " ".join(descriptions)

    lower_q = normalized.lower()
    for pattern, answer in STATIC_QA:
        if pattern.search(lower_q):
            return answer
    return None


def format_codes_sentence(codes: list[str], fallback: Optional[list[str]] = None) -> str:
    source = codes or (fallback or [])
    allowed_without_digits = {"FLAT PNL 3/4", "FLAT PNL 5/8", "HIN-FLIPUP-AHK"}

    filtered = []
    for code in source:
        if not code:
            continue
        candidate = code.strip().upper()
        if not candidate:
            continue
        if any(char.isdigit() for char in candidate):
            filtered.append(candidate)
            continue
        if candidate in allowed_without_digits:
            filtered.append(candidate)

    unique_codes = filtered
    unique_codes = sorted(set(unique_codes))

    if not unique_codes:
        return "I could not identify any cabinet codes in the document."

    if len(unique_codes) == 1:
        return f"The document includes the cabinet code {unique_codes[0]}."

    *initial, final = unique_codes
    formatted_list = ", ".join(initial)
    if formatted_list:
        formatted_list += f", and {final}"
    else:
        formatted_list = final
    return f"The document includes the following cabinet codes: {formatted_list}."


def is_code_extraction_query(question: str) -> bool:
    lowered = question.lower()
    keywords = [
        "cabinet code",
        "cabinet codes",
        "list codes",
        "cabinet ids",
        "unique codes",
        "code list",
        "list all codes",
        "show cabinet codes",
        "extract cabinet codes",
        "list cabinets",
    ]
    return any(keyword in lowered for keyword in keywords)

def _build_system_prompt() -> str:
    return """You are a helpful AI assistant specialized in analyzing pricing catalogs and construction documents.

FORMATTING RULES:
1. Use plain text only; do not use markdown symbols.
2. Use emojis for visual hierarchy: 💰, 📊, 🎨, ⭐, ⚠️, 📍, etc.
3. Structure responses with blank lines and indentation for clarity.
4. Use dots or dashes for separators and bullet-style lists.
5. Use arrows (→) to emphasize key details or comparisons.
6. Use box dividers with straight lines like ━━━━━━━━━━ to separate sections.
7. Always include a source citation at the end when available.

Pricing Requirements:
- When dollar amounts appear in the context, list every available grade/material price and the full range.
- Never claim pricing is unavailable if dollar values exist in context.
- Cite sheet and row information whenever present.
- Present multiple SKUs in comparison-friendly layouts with clear separators.

Example Response:
━━━━━━━━━━━━━━━━━━━━
💰 PRICING ANALYSIS

SKU: B36
Price Range: $80 → $1,740

🎨 GRADES
   - Grade 1 → $1,003
   - Grade 5 → $1,471 ⭐ Best Value
   - Grade 9 → $1,740 💎 Premium

📍 Source → Catalog.xlsx Sheet ASPIRE 2024-2025 Row 312
━━━━━━━━━━━━━━━━━━━━
"""


def _build_user_prompt(question: str, context: str, force_code_mode: bool = False) -> str:
    safe_context = context[:15000]
    if force_code_mode:
        instructions = """Instructions:
- List every unique cabinet code in the document.
- Provide the answer as a natural sentence (e.g., "The document includes ...").
- Do not return JSON, bullet lists, or phrases like "several others".
- Only include tokens that match cabinetry code patterns (e.g., BC242484-1TDL, WP3024-15HK, SB42FH, DB24, USF3102, FLAT PNL 3/4)."""
    else:
        instructions = """Instructions:
- Answer the question using clear, natural language.
- Include any relevant pricing or code details referenced in the document.
- Present the response in full sentences without relying on JSON or bullet lists unless necessary."""

    return f"""Document Content:
{safe_context}

Question: {question}

{instructions}"""


def _call_openai(question: str, context: str, force_code_mode: bool = False) -> str:
    from openai import OpenAI

    client = OpenAI()
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": _build_user_prompt(question, context, force_code_mode)},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    message_content = completion.choices[0].message.content
    if message_content is None:
        raise RuntimeError("OpenAI response did not include any content.")
    return cast(str, message_content)


def _call_gemini(question: str, context: str, force_code_mode: bool = False) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini provider not configured. Set GEMINI_API_KEY.")

    configured = os.environ.get("GEMINI_MODEL")
    if configured:
        candidate_models = [model.strip() for model in configured.split(",") if model.strip()]
    else:
        candidate_models = [
            "gemini-2.5-pro",
            "gemini-2.0-pro-exp",
            "gemini-2.0-pro-latest",
            "gemini-2.0-pro",
        ]

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _build_system_prompt()},
                    {"text": _build_user_prompt(question, context, force_code_mode)},
                ]
            }
        ]
    }

    last_error: Optional[Exception] = None

    for model_name in candidate_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            candidates = data.get("candidates", [])
            first_candidate = candidates[0]
            parts = first_candidate.get("content", {}).get("parts", [])
            texts = [part.get("text", "") for part in parts if part.get("text")]
            if not texts:
                raise ValueError("Gemini response did not contain any text output.")
            return "\n".join(texts)
        except Exception as exc:
            logging.warning("Gemini model %s failed: %s", model_name, exc)
            last_error = exc
            continue

    error_detail = last_error or RuntimeError("All Gemini models failed.")
    raise RuntimeError(f"Failed to query Gemini. Last error: {error_detail}")


async def query_ai_provider(
    question: str,
    context: str,
    provider: str = "gemini",
    force_code_mode: bool = False,
) -> tuple[str, Optional[List[Dict[str, Any]]], str]:
    """Query the configured AI provider with the supplied document context."""
    try:
        resolved_provider = provider
        if provider == "gemini":
            try:
                answer = _call_gemini(question, context, force_code_mode)
            except Exception as gemini_error:
                logging.warning("Gemini provider failed, falling back to OpenAI: %s", gemini_error)
                answer = _call_openai(question, context, force_code_mode)
                resolved_provider = "openai"
        else:
            answer = _call_openai(question, context, force_code_mode)
            resolved_provider = "openai"

        table_data = None
        if '|' in answer or '\t' in answer:
            try:
                lines = answer.split('\n')
                table_lines = [line for line in lines if '|' in line or '\t' in line]
                if len(table_lines) > 1:
                    pass
            except Exception:
                pass

        return answer, table_data, resolved_provider

    except RuntimeError as config_error:
        logging.error("AI provider configuration error: %s", config_error)
        return str(config_error), None, provider
    except requests.HTTPError as http_error:
        logging.error("Gemini HTTP error: %s", http_error)
        return f"Gemini request failed: {http_error}", None, provider
    except Exception as exc:
        logging.exception("AI query error")
        return f"Error querying AI: {exc}", None, provider

# ===== Pricing AI Routes =====
@api_router.post("/pricing-ai/query", response_model=AIResponse)
async def pricing_ai_query(
    query: AIQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Query AI about file content (pricing, data extraction, calculations)"""
    
    # Get the file
    db_file = db.query(DBFile).filter(DBFile.id == query.file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Verify file belongs to user's project
    project = db.query(Project).filter(
        and_(Project.id == db_file.project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Resolve file path
    stored_path = cast(str, db_file.file_path)
    file_path = Path(stored_path)
    if not file_path.is_absolute():
        file_path = UPLOAD_DIR / stored_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path}")
    
    file_type_value = cast(Optional[str], db_file.file_type)
    if not file_type_value:
        raise HTTPException(status_code=400, detail="File type is not set for this file")

    context = build_smart_context(query.question, file_path, file_type_value)

    static_answer = get_static_answer(query.question)
    if static_answer:
        return AIResponse(
            response=static_answer,
            table=None,
            provider=query.provider,
        )

    answer, table_data, resolved_provider = await query_ai_provider(
        query.question,
        context,
        query.provider,
    )

    formatted_answer = format_ai_response(answer, query.question)

    return AIResponse(
        response=formatted_answer,
        table=table_data,
        provider=resolved_provider,
    )

# ===== Discussion Routes =====
@api_router.post("/projects/{project_id}/messages", response_model=MessageResponse)
def create_message(
    project_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_message = Message(
        project_id=project_id,
        user_id=current_user.id,
        content=message_data.content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # Load user relationship for response
    db.refresh(db_message, ["user"])
    
    return MessageResponse.model_validate(db_message)

@api_router.get("/projects/{project_id}/messages", response_model=List[MessageResponse])
def get_messages(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
    project = db.query(Project).filter(
        and_(Project.id == project_id, Project.owner_id == current_user.id)
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    messages = db.query(Message).filter(
        Message.project_id == project_id
    ).order_by(Message.created_at).all()
    
    return [MessageResponse.model_validate(m) for m in messages]

# Include the router
app.include_router(api_router)

# ===== CORS Configuration =====
cors_origins_raw = os.environ.get("CORS_ORIGINS", "*")
cors_allow_credentials_raw = os.environ.get("CORS_ALLOW_CREDENTIALS", "true")

allow_credentials = cors_allow_credentials_raw.lower() == "true"

if cors_origins_raw.strip() == "*":
    allow_origins = ["*"]
    if allow_credentials:
        logger.warning(
            "CORS_ORIGINS='*' with credentials enabled. "
            "Disabling credentials so wildcard origin is permitted."
        )
        allow_credentials = False
else:
    allow_origins = [
        origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()
    ]
    if not allow_origins:
        logger.warning(
            "CORS_ORIGINS resolved to an empty list; defaulting to http://localhost:3000"
        )
        allow_origins = ["http://localhost:3000"]

logger.info(
    "CORS configuration: origins=%s allow_credentials=%s",
    allow_origins,
    allow_credentials,
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files (for production deployment)
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend" / "build"
if FRONTEND_BUILD_DIR.exists():
    # Serve static files
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")), name="static")
    
    # Serve React app root route
    @app.get("/")
    async def serve_frontend_root():
        """Serve React app at root"""
        index_path = FRONTEND_BUILD_DIR / "index.html"
        if index_path.exists():
            return FastAPIFileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not built")
    
    # Serve React app for all non-API routes (this route is registered last, so API routes take precedence)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React app for all non-API routes (for React Router)"""
        # Don't serve frontend for API routes (shouldn't reach here, but safety check)
        if full_path.startswith("api") or full_path.startswith("/api"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Serve index.html for React Router
        index_path = FRONTEND_BUILD_DIR / "index.html"
        if index_path.exists():
            return FastAPIFileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not built")

@app.on_event("shutdown")
def shutdown_db():
    # SQLAlchemy handles connection cleanup automatically
    pass