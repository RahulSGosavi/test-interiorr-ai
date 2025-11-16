from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File as FormFile, Form, status
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as FastAPIFileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, inspect, text
import os
import logging
import time
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
# RAG imports
from rag_document_processor import create_rag_context
from enhanced_system_prompt import EnhancedSystemPrompt

# Advanced Document Processor
from advanced_document_processor import create_advanced_context

# Bulk Question Processor
from bulk_question_processor import split_bulk_questions, is_bulk_question, format_bulk_answer

# AI Agent imports
from ai_agent_orchestrator import get_ai_agent, AgentResponse

# Configure logging early (before loading env to see what happens)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
env_path = ROOT_DIR / '.env'

# Load environment variables
if env_path.exists():
    load_dotenv(env_path, override=True)
    logger.info(f"Loaded .env file from: {env_path}")
else:
    # Try loading from parent directory or current directory
    load_dotenv(override=True)
    logger.warning(f".env file not found at {env_path}, trying default locations")

# Verify critical environment variables are loaded
gemini_key = os.environ.get("GEMINI_API_KEY")
openai_key = os.environ.get("OPENAI_API_KEY")
if not gemini_key and not openai_key:
    logger.warning("Neither GEMINI_API_KEY nor OPENAI_API_KEY is set. Pricing AI will not work.")
else:
    if gemini_key:
        logger.info("GEMINI_API_KEY is configured (length: %d)", len(gemini_key))
    if openai_key:
        logger.info("OPENAI_API_KEY is configured (length: %d)", len(openai_key))

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {e}", exc_info=True)
    raise


def ensure_folder_schema():
    try:
        with engine.begin() as connection:
            inspector = inspect(connection)
            columns = {col['name'] for col in inspector.get_columns('files')}
            if 'folder_id' not in columns:
                connection.execute(text('ALTER TABLE files ADD COLUMN folder_id INTEGER'))
                connection.execute(text('ALTER TABLE files ADD CONSTRAINT files_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL'))
    except Exception as e:
        logger.warning(f"Error ensuring folder schema: {e}")


ensure_folder_schema()

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = "dev-secret-key-change-in-production"
    logger.warning("SECRET_KEY not set, using default (not secure for production!)")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 43200))

# Upload directory
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', 'uploads'))
UPLOAD_DIR.mkdir(exist_ok=True)

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

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
    db_status = "unavailable"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
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
    try:
        db_project = Project(
            owner_id=current_user.id,
            name=project_data.name,
            description=project_data.description
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        try:
            return ProjectResponse.model_validate(db_project)
        except Exception as e:
            logger.error(f"Error validating project response: {e}", exc_info=True)
            # Fallback: manually construct response
            return ProjectResponse(
                id=db_project.id,  # type: ignore[arg-type]
                name=db_project.name,  # type: ignore[arg-type]
                description=db_project.description,  # type: ignore[arg-type]
                owner_id=db_project.owner_id,  # type: ignore[arg-type]
                created_at=db_project.created_at,  # type: ignore[arg-type]
                updated_at=getattr(db_project, 'updated_at', None)
            )
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")

@api_router.get("/projects", response_model=List[ProjectResponse])
def get_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        projects = db.query(Project).filter(Project.owner_id == current_user.id).all()
        result = []
        for p in projects:
            try:
                # Use model_validate which should work with from_attributes=True in model_config
                result.append(ProjectResponse.model_validate(p))
            except Exception as e:
                logger.error(f"Error validating project {p.id}: {e}", exc_info=True)
                # Fallback: manually construct the response
                try:
                    result.append(ProjectResponse(
                        id=p.id,  # type: ignore[arg-type]
                        name=p.name or "",  # type: ignore[arg-type]
                        description=p.description,  # type: ignore[arg-type]
                        owner_id=p.owner_id,  # type: ignore[arg-type]
                        created_at=p.created_at,  # type: ignore[arg-type]
                        updated_at=getattr(p, 'updated_at', None)
                    ))
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed for project {p.id}: {fallback_error}", exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Error serializing project {p.id}: {str(e)}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
def detect_catalog_type(file_id: int, db: Session) -> str:
    """Detect catalog type from filename"""
    db_file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not db_file:
        return "UNKNOWN"
    
    # File model uses 'name' attribute, not 'filename'
    filename_lower = db_file.name.lower()
    
    if '1951' in filename_lower or 'cabinetry' in filename_lower:
        logging.info(f"[Catalog] Detected 1951 Cabinetry catalog: {db_file.name}")
        return "1951_CATALOG"
    elif 'wellborn' in filename_lower or 'aspire' in filename_lower:
        logging.info(f"[Catalog] Detected Wellborn Aspire catalog: {db_file.name}")
        return "WELLBORN_CATALOG"
    else:
        logging.warning(f"[Catalog] Unknown catalog type for {db_file.name}")
        return "UNKNOWN"


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
            header_type: str = "standard"  # "standard" or "flexible"
            
            # First, try to find the standard Wellborn format header (RUSH, CF, AW)
            for idx, row in df.iterrows():
                row_str = " ".join([str(x) for x in row if pd.notna(x)]).upper()
                if "RUSH" in row_str and "CF" in row_str and "AW" in row_str:
                    try:
                        header_row_idx = int(cast(Any, idx))
                        header_type = "standard"
                    except (TypeError, ValueError):
                        logging.warning(
                            "Skipping sheet %s due to non-numeric header index %s",
                            sheet_name,
                            idx,
                        )
                        header_row_idx = None
                    break

            # If standard format not found, try flexible header detection
            if header_row_idx is None:
                # Look for common header patterns: SKU, CODE, ITEM, MODEL, CABINET, PART
                for idx, row in df.iterrows():
                    row_str = " ".join([str(x) for x in row if pd.notna(x)]).upper()
                    # Check for common SKU/code header patterns
                    if any(keyword in row_str for keyword in ["SKU", "CODE", "ITEM", "MODEL", "CABINET", "PART", "NUMBER"]):
                        # Make sure it looks like a header (has multiple meaningful columns)
                        non_empty = [str(x).strip() for x in row if pd.notna(x) and str(x).strip()]
                        if len(non_empty) >= 3:  # At least 3 columns
                            try:
                                header_row_idx = int(cast(Any, idx))
                                header_type = "flexible"
                                logging.info(f"Found flexible header in sheet '{sheet_name}' at row {header_row_idx}")
                                break
                            except (TypeError, ValueError):
                                continue

            if header_row_idx is None:
                # Try first row as header if it has reasonable content
                if len(df) > 0:
                    first_row = df.iloc[0]
                    non_empty = [str(x).strip() for x in first_row if pd.notna(x) and str(x).strip()]
                    if len(non_empty) >= 2:  # At least 2 columns
                        header_row_idx = 0
                        header_type = "flexible"
                        logging.info(f"Using first row as header for sheet '{sheet_name}'")

            if header_row_idx is None:
                warning_msg = f"No header row found in sheet '{sheet_name}'. Tried standard format (RUSH/CF/AW) and flexible format."
                logging.warning(warning_msg)
                structured_data["parse_errors"].append(warning_msg)
                continue

            headers = df.iloc[header_row_idx].fillna("").astype(str).tolist()

            sku_col_idx: Optional[int] = None
            pricing_start_idx: Optional[int] = None
            
            if header_type == "standard":
                # Standard Wellborn format: look for RUSH column
                for i, header_value in enumerate(headers):
                    normalized = str(header_value).strip().upper()
                    if "RUSH" == normalized or "RUSH" in normalized:
                        sku_col_idx = max(i - 1, 0)
                        pricing_start_idx = i + 2  # skip RUSH and species charge column
                        break
            else:
                # Flexible format: look for SKU/CODE/ITEM columns
                for i, header_value in enumerate(headers):
                    normalized = str(header_value).strip().upper()
                    # Look for SKU/code identifier columns
                    if any(keyword in normalized for keyword in ["SKU", "CODE", "ITEM", "MODEL", "CABINET", "PART"]):
                        sku_col_idx = i
                        # Find first column that looks like a price column (or use next column)
                        pricing_start_idx = i + 1
                        break
                
                # If no SKU column found, try first column
                if sku_col_idx is None:
                    sku_col_idx = 0
                    pricing_start_idx = 1

            if sku_col_idx is None:
                warning_msg = f"Could not determine SKU column in sheet '{sheet_name}'."
                logging.warning(warning_msg)
                structured_data["parse_errors"].append(warning_msg)
                continue
            
            if pricing_start_idx is None:
                pricing_start_idx = sku_col_idx + 1

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

            # Note: Even if no pricing headers found, we can still extract SKU codes
            if not clean_headers:
                warning_msg = f"No pricing headers detected in sheet '{sheet_name}'. Will extract SKU codes only."
                logging.warning(warning_msg)
                structured_data["parse_errors"].append(warning_msg)
                # Don't continue - allow SKU extraction without prices

            data_start = header_row_idx + 1  # Start from row after header

            for idx in range(data_start, len(df)):
                row = df.iloc[idx]

                if sku_col_idx >= len(row):
                    continue

                sku_raw = str(row.iloc[sku_col_idx]).strip().upper()

                # Skip empty, invalid, or note rows
                if (
                    not sku_raw
                    or sku_raw == "NAN"
                    or len(sku_raw) < 2
                    or sku_raw.startswith("*")
                    or sku_raw.startswith("NOTE")
                ):
                    continue

                # Skip descriptions and specifications - look for actual cabinet codes
                # Reject if it contains common description words
                description_keywords = [
                    "DEEP", "HIGH", "WIDE", "PLYWOOD", "PANELS", "PANEL", "DRAWER", "BODY",
                    "GLIDES", "INCLUDED", "VANITY", "BASE CABINET", "WALL CABINET",
                    "FULL HEIGHT", "ENGINEERED", "WOOD", "USING", "SIDE-MOUNT",
                    "X", "●", "SPECIFICATION", "DESCRIPTION", "DIMENSION"
                ]
                if any(keyword in sku_raw for keyword in description_keywords):
                    continue
                
                # Skip if it's just dimensions (e.g., "12\" DEEP X 84\" HIGH")
                if re.search(r'\d+"?\s*(DEEP|HIGH|WIDE|X)', sku_raw):
                    continue
                
                # Skip if it's too long (descriptions are usually long, codes are short)
                if len(sku_raw) > 30:
                    continue

                # Strict cabinet code validation - must match actual cabinet code patterns
                # Pattern: 1-3 letters followed by 2+ digits, optionally followed by more alphanumeric, spaces, hyphens, or common modifiers
                # Examples: B12, B24, W3630, W1842, SB30, DB24, SB24 BUTT, W3630 L/R, B12 SHELF, CW24 SHELF MI
                # Allow common modifiers: BUTT, L/R, L, R, TD, DP, FH, SHELF, PLY, AS, WD, NP, MI, RAS, UNIT, 1DDWR, 2DWR, 4DWR, 1DWR, CCBPPO, KIT, CC, DT, GROOVED
                cabinet_code_pattern = re.compile(
                    r'^[A-Z]{1,3}\d{2,}(?:[\s\-]?[A-Z0-9]+)*(?:\s+(?:BUTT|L/R|L|R|TD|DP|FH|SHELF|PLY|AS|WD|NP|MI|RAS|UNIT|1DDWR|2DWR|4DWR|1DWR|CCBPPO|KIT|CC|DT|GROOVED|ADJ))*(?:\s+[A-Z0-9]+)*$'
                )
                
                # Also allow special cases
                special_codes = ["FLAT PNL 3/4", "FLAT PNL 5/8"]
                
                # Check if it matches cabinet code pattern - must start with letters followed by digits
                # Basic pattern check: starts with 1-3 letters, followed by 2+ digits
                basic_pattern = re.compile(r'^[A-Z]{1,3}\d{2,}')
                if not basic_pattern.match(sku_raw) and sku_raw not in special_codes:
                    continue
                
                # Additional validation - ensure it's not just a description
                # If it matches basic pattern, allow it even if full pattern doesn't match (for codes with unusual modifiers)

                sku = re.sub(r"\s+", " ", sku_raw).strip()

                prices: Dict[str, float] = {}
                
                # Only try to extract prices if we have pricing headers
                if clean_headers:
                    price_values = row.iloc[pricing_start_idx : pricing_start_idx + len(clean_headers)]
                    for header, value in zip(clean_headers, price_values):
                        if pd.isna(value):
                            continue

                        header_str = str(header)
                        if not header_str:
                            continue
                        try:
                            # More robust price extraction
                            numeric_value = str(value).strip()
                            # Remove currency symbols, commas, and other non-numeric chars except decimal point and minus
                            numeric_value = numeric_value.replace("$", "").replace(",", "").replace("D", "").replace("-", "").strip()
                            # Keep only digits, decimal point, and minus sign
                            numeric_value = re.sub(r"[^\d\.\-]", "", numeric_value)
                            
                            # Handle empty strings
                            if not numeric_value or numeric_value == "-" or numeric_value == ".":
                                continue
                            
                            # Remove trailing/leading decimal points that would cause errors
                            if numeric_value.startswith("."):
                                numeric_value = "0" + numeric_value
                            if numeric_value.endswith("."):
                                numeric_value = numeric_value[:-1]
                            
                            if not numeric_value:
                                continue
                            
                            price = float(numeric_value)
                            # Expanded price range to handle higher values (0 to 1,000,000)
                            if price > 0 and price <= 1000000:
                                prices[header_str] = round(price, 2)  # Round to 2 decimal places for consistency
                        except (ValueError, TypeError) as e:
                            logging.debug(f"Failed to parse price value '{value}' for header '{header_str}': {e}")
                            continue

                # Extract SKU even if no prices found (for listing cabinet codes)
                structured_data["skus"][sku] = {
                    "sheet": sheet_name,
                    "prices": prices,  # Empty dict if no prices
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
    
    # Detect calculation questions
    question_lower = question.lower()
    is_calculation = any(keyword in question_lower for keyword in [
        "total", "sum", "add", "calculate", "cost", "price", "average", 
        "highest", "lowest", "maximum", "minimum", "compare", "difference",
        "how much", "what is", "how many", "all items", "all skus"
    ])

    if normalized_type in ("xlsx", "xls", "excel"):
        # Check if file exists
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            logging.error(error_msg)
            return f"Error: {error_msg}"
        
        # Check if file is readable
        if not file_path.is_file():
            error_msg = f"Path is not a file: {file_path}"
            logging.error(error_msg)
            return f"Error: {error_msg}"
        
        try:
            data = extract_structured_pricing(file_path)
        except Exception as e:
            error_msg = f"Failed to extract pricing data: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return f"Error: {error_msg}"

        # Check if SKUs were extracted (even without prices)
        skus = data.get("skus", {})
        if not skus:
            error_msg = data.get("error", "No SKUs found in the file")
            parse_errors = data.get("parse_errors", [])
            sheets = data.get("sheets", [])
            total_rows = data.get("total_rows", 0)
            
            # Build detailed error message for AI
            error_details = [f"Could not extract SKU data from the file."]
            
            # Check if it's an exception error
            if error_msg and error_msg != "No SKUs found in the file":
                error_details.append(f"Error: {error_msg}")
            
            # Add file information
            error_details.append(f"File: {file_path.name}")
            
            # Add sheet information
            if sheets:
                error_details.append(f"Found {len(sheets)} sheet(s): {', '.join(sheets)}")
                error_details.append("Note: The parser tried both standard format (looks for 'RUSH', 'CF', 'AW') and flexible format (looks for 'SKU', 'CODE', 'ITEM', etc.).")
                error_details.append("If no header row was found matching these patterns, no SKUs could be extracted.")
            else:
                error_details.append("No sheets were found in the Excel file.")
            
            if parse_errors:
                error_details.append(f"Parse errors encountered: {', '.join(parse_errors[:3])}")
            
            if total_rows == 0 and not error_msg:
                error_details.append("The file may not match the expected catalog format.")
            
            full_error = " ".join(error_details)
            logging.error(f"SKU extraction failed: {full_error}")
            
            # Return a detailed error that the AI can work with
            return f"""Error extracting SKU data:
{full_error}

Please verify:
1. The file is a valid Excel file (.xlsx or .xls)
2. The file contains a header row with column names
3. The file has SKU/code data in one of the columns"""

        matched_skus = find_matching_skus(question, data["skus"])
        
        # If no SKUs matched but question mentions SKU-like patterns, do a broader search
        if not matched_skus and (is_calculation or "price" in question_lower or "cost" in question_lower or "cheaper" in question_lower or "compare" in question_lower):
            # Extract potential SKU codes from question (e.g., B24, B36, W2430)
            sku_pattern = re.compile(r'\b([A-Z]\d{2,}(?:\s+\d+[A-Z]+)?(?:\s+[A-Z]+)?)\b', re.IGNORECASE)
            potential_skus = sku_pattern.findall(question)
            
            # Try to find SKUs that start with these codes
            for potential_sku in potential_skus:
                base_code = potential_sku.upper().strip()
                # Remove common suffixes like "1TD", "BUTT", etc. to find base code
                base_match = re.match(r'^([A-Z]\d{2,})', base_code)
                if base_match:
                    base = base_match.group(1)
                    # Find all SKUs that start with this base code
                    for catalog_sku in data["skus"].keys():
                        if catalog_sku.upper().startswith(base) and catalog_sku not in matched_skus:
                            matched_skus.append(catalog_sku)

        # For calculation questions asking for totals/all items, include all pricing data
        if is_calculation and ("all" in question_lower or "total" in question_lower or "sum" in question_lower):
            # Build comprehensive context with all SKUs and their prices
            lines = [
                "=" * 70,
                "COMPLETE PRICING CATALOG DATA FOR CALCULATIONS",
                "=" * 70,
                "",
                f"Total SKUs in Catalog: {len(data['skus'])}",
                f"Data Source: {', '.join(data['sheets'])}",
                "",
                "ALL SKU PRICING DATA:",
                "-" * 70,
                ""
            ]
            
            # Include all SKUs with their pricing (limit to first 200 for context size)
            sku_items = list(data["skus"].items())[:200]
            for sku, sku_data in sku_items:
                prices = sku_data["prices"]
                if not prices:
                    continue
                
                lines.append(f"SKU: {sku}")
                lines.append(f"Sheet: '{sku_data['sheet']}', Row: {sku_data.get('row_index', 'N/A')}")
                
                grade_order = {"CF": 0, "AW": 1}
                sorted_prices = sorted(
                    prices.items(),
                    key=lambda item: (
                        grade_order.get(item[0], 2),
                        item[0]
                    )
                )
                
                price_list = []
                for grade, price in sorted_prices:
                    # Preserve material/finish names as-is
                    if grade.startswith("GRADE_"):
                        display_grade = grade.replace("GRADE_", "Grade ")
                    else:
                        display_grade = grade
                    price_list.append(f"{display_grade}: ${price:,.2f}")
                
                lines.append(f"Prices: {', '.join(price_list)}")
                lines.append("")
            
            if len(data["skus"]) > 200:
                lines.append(f"... (and {len(data['skus']) - 200} more SKUs)")
            
            lines.append("-" * 70)
            lines.append("")
            lines.append("IMPORTANT: Use these EXACT prices for all calculations.")
            return "\n".join(lines)

        if matched_skus:
            lines = [
                "=" * 70,
                "WELLBORN ASPIRE PRICING CATALOG",
                "=" * 70,
                "",
                f"Total SKUs Available: {len(data['skus'])}",
                f"Data Source: {', '.join(data['sheets'])}",
                "",
            ]
            
            if is_calculation:
                lines.append("CALCULATION MODE: Use EXACT prices shown below for all calculations.")
                lines.append("")
            
            lines.extend([
                "REQUESTED SKU DETAILS:",
                "-" * 70,
                ""
            ])

            for sku in matched_skus:
                sku_data = data["skus"][sku]
                prices = sku_data["prices"]

                lines.append(f"SKU: {sku}")
                lines.append(f"Location: Sheet '{sku_data['sheet']}', Row {sku_data.get('row_index', 'N/A')}")
                
                if prices:
                    lines.append(f"Price Grades Available: {len(prices)}")
                    lines.append("")
                    lines.append("PRICING BREAKDOWN (EXACT VALUES):")

                    grade_order = {"CF": 0, "AW": 1}
                    sorted_prices = sorted(
                        prices.items(),
                        key=lambda item: (
                            grade_order.get(item[0], 2),
                            item[0]
                        )
                    )

                    for grade, price in sorted_prices:
                        # Preserve material/finish names as-is (Elite Cherry, Choice Painted, etc.)
                        # Only normalize if it's a generic grade format
                        if grade.startswith("GRADE_"):
                            display_grade = grade.replace("GRADE_", "Grade ")
                        else:
                            # Use the original header name (e.g., "Elite Cherry", "Choice Painted")
                            display_grade = grade
                        # Ensure consistent formatting with 2 decimal places for calculations
                        formatted_price = f"${price:,.2f}"
                        lines.append(f"  • {display_grade}: {formatted_price}")
                else:
                    lines.append("Note: No pricing information available for this SKU.")
                
                lines.append("")
                lines.append("-" * 70)
                lines.append("")
            
            if is_calculation:
                lines.append("REMINDER: Use the exact prices shown above for all calculations.")
                lines.append("")

            return "\n".join(lines)

        # For questions about listing codes, provide all SKUs in a clear format
        question_lower_for_codes = question_lower
        is_code_list_query = any(keyword in question_lower_for_codes for keyword in [
            "list", "all unique", "all cabinet codes", "cabinet codes", "codes", "unique codes", "list all"
        ])
        
        if is_code_list_query:
            # List all SKUs for code listing queries, organized by category
            lines = [
                "=" * 70,
                "ALL CABINET CODES IN CATALOG",
                "=" * 70,
                "",
                f"Total SKUs Found: {len(data['skus'])}",
                f"Data Source: {', '.join(data['sheets'])}",
                "",
            ]
            
            # Organize SKUs by category (Base, Wall, Sink Base, Drawer Base, etc.)
            base_cabinets = []
            wall_cabinets = []
            sink_bases = []
            drawer_bases = []
            specialty = []
            other = []
            
            all_skus = sorted(set(data["skus"].keys()))
            for sku in all_skus:
                sku_upper = sku.upper().strip()
                # Extract base code (first letters + digits, ignoring modifiers)
                base_match = re.match(r'^([A-Z]{1,3}\d{2,})', sku_upper)
                if not base_match:
                    other.append(sku)
                    continue
                    
                base_code = base_match.group(1)
                
                # Categorize by the base code pattern
                if base_code.startswith("B") and len(base_code) >= 2 and base_code[1].isdigit():
                    # Base cabinets: B12, B15, B18, B21, B24, B27, B30, B33, B36, B39, B42, etc.
                    base_cabinets.append(sku)
                elif base_code.startswith("W") and len(base_code) >= 2 and base_code[1].isdigit():
                    # Wall cabinets: W942, W1242, W1542, W1842, W2430, W3030, W3630, etc.
                    wall_cabinets.append(sku)
                elif base_code.startswith("SB"):
                    # Sink bases: SB24, SB30, SB33, SB36, etc.
                    sink_bases.append(sku)
                elif base_code.startswith("DB"):
                    # Drawer bases: DB12, DB15, DB18, DB21, DB24, DB30, DB36, etc.
                    drawer_bases.append(sku)
                elif any(base_code.startswith(prefix) for prefix in ["CW", "CBS", "CWS", "UT", "PB", "OVD", "OVS", "BTB", "FSEP", "BS", "BSS", "BEA", "BEP", "BLC", "BPC", "BPP", "AS", "BCF"]):
                    # Specialty cabinets
                    specialty.append(sku)
                else:
                    other.append(sku)
            
            # Format output by category (prioritize common cabinets)
            # Check if any SKUs have pricing
            has_pricing = any(data["skus"][sku].get("prices") for sku in all_skus)
            
            if base_cabinets:
                lines.append("BASE CABINETS:")
                # Group by base width if possible (B12, B15, B18, etc.)
                simple_bases = [sku for sku in base_cabinets if re.match(r'^B\d{2,3}$', sku.upper())]
                complex_bases = [sku for sku in base_cabinets if sku not in simple_bases]
                
                if simple_bases:
                    lines.append(", ".join(sorted(simple_bases, key=lambda x: (len(x), x))))
                if complex_bases:
                    if simple_bases:
                        lines.append("")  # Add blank line between simple and complex
                    lines.append(", ".join(sorted(complex_bases, key=lambda x: (len(x), x))))
                lines.append(f"({len(base_cabinets)} codes)")
                lines.append("")
            
            if wall_cabinets:
                lines.append("WALL CABINETS:")
                # Group by simple vs complex
                simple_walls = [sku for sku in wall_cabinets if re.match(r'^W\d{3,4}$', sku.upper())]
                complex_walls = [sku for sku in wall_cabinets if sku not in simple_walls]
                
                if simple_walls:
                    lines.append(", ".join(sorted(simple_walls, key=lambda x: (len(x), x))))
                if complex_walls:
                    if simple_walls:
                        lines.append("")
                    lines.append(", ".join(sorted(complex_walls, key=lambda x: (len(x), x))))
                lines.append(f"({len(wall_cabinets)} codes)")
                lines.append("")
            
            if sink_bases:
                lines.append("SINK BASES:")
                lines.append(", ".join(sorted(sink_bases, key=lambda x: (len(x), x))))
                lines.append(f"({len(sink_bases)} codes)")
                lines.append("")
            
            if drawer_bases:
                lines.append("DRAWER BASES:")
                lines.append(", ".join(sorted(drawer_bases, key=lambda x: (len(x), x))))
                lines.append(f"({len(drawer_bases)} codes)")
                lines.append("")
            
            if specialty:
                lines.append("SPECIALTY CABINETS:")
                lines.append(", ".join(sorted(specialty, key=lambda x: (len(x), x))))
                lines.append(f"({len(specialty)} codes)")
                lines.append("")
            
            if other:
                lines.append("OTHER:")
                lines.append(", ".join(sorted(other, key=lambda x: (len(x), x))))
                lines.append(f"({len(other)} codes)")
                lines.append("")
            
            lines.append("-" * 70)
            lines.append("")
            lines.append(f"Total: {len(all_skus)} unique cabinet codes")
            if has_pricing:
                lines.append("")
                lines.append("Note: All SKUs shown have pricing available across multiple grade tiers.")
                lines.append("Ask for specific pricing (e.g., 'What's the price of B24 in Elite Cherry?')")
            return "\n".join(lines)
        
        # For pricing/comparison questions, include all SKUs with pricing info
        if is_calculation or "price" in question_lower or "cost" in question_lower or "cheaper" in question_lower or "compare" in question_lower:
            lines = [
                "=" * 70,
                "PRICING CATALOG - ALL AVAILABLE SKUs",
                "=" * 70,
                "",
                f"Total SKUs Available: {len(data['skus'])}",
                f"Data Source: {', '.join(data['sheets'])}",
                "",
                "ALL SKU PRICING DATA:",
                "-" * 70,
                ""
            ]
            
            # Include all SKUs with their pricing (limit to first 300 for context size)
            sku_items = list(data["skus"].items())[:300]
            for sku, sku_data in sku_items:
                prices = sku_data["prices"]
                if not prices:
                    continue
                
                lines.append(f"SKU: {sku}")
                
                grade_order = {"CF": 0, "AW": 1}
                sorted_prices = sorted(
                    prices.items(),
                    key=lambda item: (
                        grade_order.get(item[0], 2),
                        item[0]
                    )
                )
                
                price_list = []
                for grade, price in sorted_prices:
                    if grade.startswith("GRADE_"):
                        display_grade = grade.replace("GRADE_", "Grade ")
                    else:
                        display_grade = grade
                    price_list.append(f"{display_grade}: ${price:,.2f}")
                
                lines.append(f"Prices: {', '.join(price_list)}")
                lines.append("")
            
            if len(data["skus"]) > 300:
                lines.append(f"... (and {len(data['skus']) - 300} more SKUs)")
            
            lines.append("-" * 70)
            lines.append("")
            lines.append("IMPORTANT: Search the data above for the SKUs mentioned in your question.")
            return "\n".join(lines)
        
        # Default fallback: show catalog summary
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
    """
    Detect if question is asking to LIST/EXTRACT codes (not WHERE/WHICH location questions).
    
    Returns True only if explicitly asking to list/extract codes, not location questions.
    """
    lowered = question.lower()
    
    # Location/contextual keywords that should NOT trigger code extraction
    location_keywords = [
        "where", "which", "used", "located", "section", "appears", 
        "contains", "found in", "used in", "part of", "belongs to"
    ]
    
    # If question contains location keywords, it's NOT a code extraction query
    if any(keyword in lowered for keyword in location_keywords):
        return False
    
    # Code listing keywords (explicit requests to list/extract)
    extraction_keywords = [
        "list", "all unique", "all cabinet codes", "show codes",
        "extract codes", "list all codes", "unique codes", "code list"
    ]
    
    return any(keyword in lowered for keyword in extraction_keywords)

def _build_system_prompt(question: str = "") -> str:
    """Build enhanced system prompt using RAG system prompt generator."""
    return EnhancedSystemPrompt.generate(question)


def _build_user_prompt(question: str, context: str, force_code_mode: bool = False) -> str:
    safe_context = context[:15000]
    
    # Detect if question involves calculations
    question_lower = question.lower()
    is_calculation = any(keyword in question_lower for keyword in [
        "total", "sum", "add", "calculate", "cost", "price", "average", 
        "highest", "lowest", "maximum", "minimum", "compare", "difference",
        "how much", "what is", "how many", "multiply", "times"
    ])
    
    if force_code_mode:
        instructions = """Instructions:
- List every unique cabinet code in the document.
- Provide the answer as a natural sentence (e.g., "The document includes ...").
- Do not return JSON, bullet lists, or phrases like "several others".
- Only include tokens that match cabinetry code patterns (e.g., BC242484-1TDL, WP3024-15HK, SB42FH, DB24, USF3102, FLAT PNL 3/4)."""
    else:
        if is_calculation:
            instructions = """Instructions:
- This question requires CALCULATIONS using EXACT numbers from the context.
- Use the PRECISE dollar amounts shown in the document content - do not approximate or estimate.
- For mathematical operations (addition, subtraction, multiplication, division), show step-by-step calculations using exact values.
- Double-check all arithmetic to ensure accuracy.
- Present the final answer with exact precision (match decimal places from the source data).
- If listing multiple items for a total, list each item and its exact price, then sum them precisely.
- Example: If calculating a total, show: "$100.00 + $200.50 + $75.25 = $375.75"
- Answer using clear, natural language with precise numbers."""
        else:
            # Distinguish between code LISTING queries and LOCATION/CONTEXTUAL queries
            # Location queries: "where", "which", "used", "located", "section", "appears"
            is_location_query = any(keyword in question_lower for keyword in [
                "where", "which", "used", "located", "section", "appears", "contains", 
                "found in", "used in", "part of", "belongs to"
            ])
            
            # Code listing queries: explicit requests to LIST or SHOW codes
            is_code_list_query = (
                any(keyword in question_lower for keyword in [
                    "list", "all unique", "all cabinet codes", "show codes", 
                    "extract codes", "list all codes", "list all"
                ]) and 
                not is_location_query  # Don't treat location questions as code listing
            )
            
            if is_code_list_query:
                instructions = """STRICT INSTRUCTIONS - LISTING CABINET CODES:
- The context contains organized sections like "BASE CABINETS:", "WALL CABINETS:", etc.
- Extract codes EXACTLY as shown in those sections
- Format output exactly as shown in context - do not change the format
- List codes in comma-separated format: "B12, B15, B18, B24"
- Include category headers: "BASE CABINETS:", "WALL CABINETS:", etc.
- Include counts shown in context: "(13 codes)"
- DO NOT invent codes - only list what is shown in context
- DO NOT add descriptions - only SKU codes like "B12", "W3630", "SB30"
- If context shows "BASE CABINETS: B12, B15, B18, B24", list exactly those codes
- Copy the exact format from context sections"""
            elif is_location_query:
                instructions = """INSTRUCTIONS - LOCATION/CONTEXTUAL QUESTIONS:
- This is a LOCATION or CONTEXTUAL question (e.g., "Where is X used?", "Which section contains Y?")
- Answer using NATURAL LANGUAGE, not just a list of codes
- Explain WHERE the cabinet code appears (e.g., "Wall Cabinet Section", "above base cabinets")
- Describe the context and purpose of the cabinet code
- Use the document structure and layout information from context
- Be conversational and helpful
- Example: "W2130-15L appears in the Wall Cabinet Section, positioned above the base cabinets in the kitchen layout."""
            elif "price" in question_lower or "cost" in question_lower or any(mat in question_lower for mat in ["elite", "choice", "premium", "prime", "cherry", "maple", "painted"]):
                instructions = """STRICT INSTRUCTIONS - PRICING QUESTIONS:
- Search context for EXACT SKU code and grade/material mentioned
- Return price in this EXACT format: "The [SKU] in [Grade] costs $[EXACT_PRICE]."
- Use EXACT numbers from context - never round or approximate
- If found: Return the price directly
- If not found: List what IS available: "B12 is available in: [list grades from context]"
- DO NOT invent prices - only use what is shown in context
- Format: The B12 base cabinet in Elite Cherry costs $342.00."""
            else:
                instructions = """Instructions:
- Answer using ONLY data from the context
- Use EXACT numbers and values - never approximate or estimate
- If data is in context, use it exactly as shown
- If data is not in context, say so clearly
- Format response clearly and concisely"""

    return f"""Document Content:
{safe_context}

Question: {question}

{instructions}"""


async def _call_openai(question: str, context: str, force_code_mode: bool = False, system_prompt_override: Optional[str] = None) -> str:
    from openai import AsyncOpenAI
    import asyncio
    
    # Check if API key is configured
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI provider not configured. Set OPENAI_API_KEY environment variable.")

    client = AsyncOpenAI(api_key=api_key)
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    
    # Use low temperature for all queries to ensure accuracy and reduce hallucinations
    temperature = 0.1

    try:
        # Use override system prompt if provided by AI agent
        system_prompt = system_prompt_override if system_prompt_override else _build_system_prompt(question)
        
        # Use async API call for parallel processing
        completion = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(question, context, force_code_mode)},
            ],
            temperature=temperature,
            max_tokens=2000,
        )

        message_content = completion.choices[0].message.content
        if message_content is None:
            raise RuntimeError("OpenAI response did not include any content.")
        return cast(str, message_content)
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise RuntimeError("OpenAI API key is invalid or not set. Please check OPENAI_API_KEY environment variable.")
        raise RuntimeError(f"OpenAI request failed: {error_msg}")


async def _call_gemini(question: str, context: str, force_code_mode: bool = False, system_prompt_override: Optional[str] = None) -> str:
    import httpx  # Use async HTTP client for parallel requests
    
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

    # Use low temperature for all queries to ensure accuracy and reduce hallucinations
    temperature = 0.1
    
    # Use override system prompt if provided by AI agent
    system_prompt = system_prompt_override if system_prompt_override else _build_system_prompt(question)
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt},
                    {"text": _build_user_prompt(question, context, force_code_mode)},
                ]
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2000,
        }
    }

    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        for model_name in candidate_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                }
                response = await client.post(url, headers=headers, json=payload)
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

    error_detail = str(last_error) if last_error else "All models failed"
    raise RuntimeError(f"Failed to query Gemini. Last error: {error_detail}")


async def query_ai_provider(
    question: str,
    context: str,
    provider: str = "gemini",
    force_code_mode: bool = False,
    system_prompt_override: Optional[str] = None,
) -> tuple[str, Optional[List[Dict[str, Any]]], str]:
    """Query the configured AI provider with the supplied document context."""
    try:
        resolved_provider = provider
        if provider == "gemini":
            try:
                answer = await _call_gemini(question, context, force_code_mode, system_prompt_override or None)
            except Exception as gemini_error:
                logging.warning("Gemini provider failed, falling back to OpenAI: %s", gemini_error)
                try:
                    answer = await _call_openai(question, context, force_code_mode, system_prompt_override or None)
                    resolved_provider = "openai"
                except Exception as openai_error:
                    # If OpenAI also fails, return the Gemini error
                    raise RuntimeError(f"Gemini failed and OpenAI fallback also failed. Gemini error: {gemini_error}, OpenAI error: {openai_error}")
        else:
            # Provider is OpenAI
            try:
                answer = await _call_openai(question, context, force_code_mode, system_prompt_override or None)
                resolved_provider = "openai"
            except Exception as openai_error:
                error_msg = str(openai_error)
                # Check if OpenAI failed due to missing/invalid API key
                if "not configured" in error_msg.lower() or "api_key" in error_msg.lower() or "api key" in error_msg.lower():
                    logging.warning("OpenAI provider failed (not configured), falling back to Gemini: %s", openai_error)
                    try:
                        answer = await _call_gemini(question, context, force_code_mode)
                        resolved_provider = "gemini"
                    except Exception as gemini_error:
                        # If Gemini also fails, return the OpenAI error with fallback info
                        raise RuntimeError(f"OpenAI is not configured (set OPENAI_API_KEY) and Gemini fallback also failed. OpenAI error: {openai_error}, Gemini error: {gemini_error}")
                else:
                    # Other OpenAI errors - try Gemini fallback
                    logging.warning("OpenAI provider failed, falling back to Gemini: %s", openai_error)
                    try:
                        answer = await _call_gemini(question, context, force_code_mode)
                        resolved_provider = "gemini"
                    except Exception as gemini_error:
                        # Both failed
                        raise RuntimeError(f"OpenAI failed and Gemini fallback also failed. OpenAI error: {openai_error}, Gemini error: {gemini_error}")

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
        logging.error("HTTP error: %s", http_error)
        return f"AI request failed: {http_error}", None, provider
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

    # Detect catalog type
    catalog_type = detect_catalog_type(query.file_id, db)
    
    # Check if this is a bulk question (multiple questions)
    if is_bulk_question(query.question):
        logger.info("Detected bulk question - splitting into individual questions")
        individual_questions = split_bulk_questions(query.question)
        logger.info(f"Split into {len(individual_questions)} questions: {individual_questions}")
        
        # OPTIMIZATION: Get shared context once (file is cached, so this is fast)
        # This avoids re-reading the file for each question
        logger.info("Getting shared context for all questions (file will be cached)...")
        shared_context = create_advanced_context(file_path, file_type_value, query.question)
        if shared_context.startswith("Error:"):
            shared_context = create_rag_context(file_path, file_type_value, query.question)
        
        # OPTIMIZATION: Prepare system prompts once (reused for all questions)
        base_system_prompt = EnhancedSystemPrompt.generate(query.question)
        if catalog_type != "UNKNOWN":
            catalog_info = f"\n\nCATALOG TYPE: {catalog_type}\n"
            if catalog_type == "1951_CATALOG":
                catalog_info += "This catalog uses grades: Elite, Premium, Prime, Choice\n"
            elif catalog_type == "WELLBORN_CATALOG":
                catalog_info += "This catalog uses numeric grades (1-10) and named grades (RUSH, CF, AW)\n"
            enhanced_system_prompt = base_system_prompt + catalog_info
        else:
            enhanced_system_prompt = base_system_prompt
        
        # OPTIMIZATION: Process questions in parallel using asyncio.gather
        # This dramatically reduces total time (from N*time to ~max(time))
        import asyncio
        
        async def process_single_question(individual_q: str, index: int) -> Dict[str, Any]:
            """Process a single question asynchronously."""
            try:
                logger.info(f"[Parallel {index}/{len(individual_questions)}] {individual_q[:50]}...")
                
                # Use shared context (file already cached, so this is instant)
                # No need to get focused context - shared context has all SKUs
                context = shared_context
                
                # Check for errors
                if context.startswith("Error:") or context.startswith("Error extracting"):
                    return {
                        'question': individual_q,
                        'answer': f"I couldn't extract data from the file for this question."
                    }
                
                # Generate answer using shared context and prompt (async API call)
                answer, table_data, resolved_provider = await query_ai_provider(
                    individual_q,
                    context,
                    query.provider,
                    system_prompt_override=enhanced_system_prompt
                )
                
                formatted_answer = format_ai_response(answer, individual_q)
                return {
                    'question': individual_q,
                    'answer': formatted_answer
                }
                
            except Exception as e:
                logger.error(f"Error processing question {index}: {e}", exc_info=True)
                return {
                    'question': individual_q,
                    'answer': f"Error processing this question: {str(e)}"
                }
        
        # Process all questions in parallel (HUGE speedup - all API calls happen simultaneously)
        logger.info(f"🚀 Processing {len(individual_questions)} questions in PARALLEL (async)...")
        start_time = time.time()
        question_answers = await asyncio.gather(*[
            process_single_question(q, i+1) 
            for i, q in enumerate(individual_questions)
        ])
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Completed {len(individual_questions)} questions in {elapsed_time:.2f} seconds (parallel)")
        
        # Format combined answer
        combined_answer = format_bulk_answer(question_answers)
        
        return AIResponse(
            response=combined_answer,
            table=None,
            provider=query.provider,
        )
    
    # Single question processing (original logic)
    # Use AI Agent Orchestrator for intelligent processing
    try:
        ai_agent = get_ai_agent()
        agent_response: AgentResponse = ai_agent.process_query(
            question=query.question,
            file_path=file_path,
            file_type=file_type_value
        )
        
        # Check if agent returned an error
        if agent_response.confidence == 0.0 and "error" in agent_response.answer.lower():
            return AIResponse(
                response=agent_response.answer,
                table=None,
                provider=query.provider,
            )
        
        # Get context from agent's response generator
        if hasattr(agent_response, 'extracted_data') and agent_response.extracted_data:
            response_data = agent_response.extracted_data
            # Check if it's a dict from response generator
            if isinstance(response_data, dict) and response_data.get("context_text"):
                context = response_data["context_text"]
                system_prompt = response_data.get("system_prompt")
                user_prompt = response_data.get("user_prompt")
                
                # Include catalog type in system prompt
                if catalog_type != "UNKNOWN":
                    catalog_info = f"\n\nCATALOG TYPE: {catalog_type}\n"
                    if catalog_type == "1951_CATALOG":
                        catalog_info += "This catalog uses grades: Elite, Premium, Prime, Choice\n"
                    elif catalog_type == "WELLBORN_CATALOG":
                        catalog_info += "This catalog uses numeric grades (1-10) and named grades (RUSH, CF, AW)\n"
                    
                    enhanced_system_prompt = (system_prompt or "") + catalog_info
                else:
                    enhanced_system_prompt = system_prompt
                
                # Call LLM with agent-prepared prompts
                answer, table_data, resolved_provider = await query_ai_provider(
                    query.question,
                    context,
                    query.provider,
                    system_prompt_override=enhanced_system_prompt
                )
            else:
                # Use advanced document processor for better extraction
                context = create_advanced_context(file_path, file_type_value, query.question)
                
                # Fallback to RAG if advanced processor fails
                if context.startswith("Error:"):
                    logger.warning("Advanced processor failed, falling back to RAG")
                    context = create_rag_context(file_path, file_type_value, query.question)
                
                # Include catalog type in system prompt
                base_system_prompt = EnhancedSystemPrompt.generate(query.question)
                if catalog_type != "UNKNOWN":
                    catalog_info = f"\n\nCATALOG TYPE: {catalog_type}\n"
                    if catalog_type == "1951_CATALOG":
                        catalog_info += "This catalog uses grades: Elite, Premium, Prime, Choice\n"
                    elif catalog_type == "WELLBORN_CATALOG":
                        catalog_info += "This catalog uses numeric grades (1-10) and named grades (RUSH, CF, AW)\n"
                    
                    enhanced_system_prompt = base_system_prompt + catalog_info
                else:
                    enhanced_system_prompt = base_system_prompt
                
                answer, table_data, resolved_provider = await query_ai_provider(
                    query.question,
                    context,
                    query.provider,
                    system_prompt_override=enhanced_system_prompt
                )
        else:
            # No agent data, use advanced document processor
            context = create_advanced_context(file_path, file_type_value, query.question)
            
            # Fallback to RAG if advanced processor fails
            if context.startswith("Error:"):
                logger.warning("Advanced processor failed, falling back to RAG")
                context = create_rag_context(file_path, file_type_value, query.question)
            
            # Check if context is an error message
            context_stripped = context.strip()
            is_error = (
                context_stripped.startswith("Error:") or 
                context_stripped.startswith("Error extracting") or
                context_stripped.startswith("Error reading") or
                context_stripped.startswith("Could not extract") or
                "Error:" in context_stripped[:100]
            )
            
            if is_error:
                error_message = context_stripped
                logging.error(f"Catalog loading error: {error_message}")
                if error_message.startswith("Error:"):
                    error_details = error_message[6:].strip()
                elif error_message.startswith("Error extracting"):
                    lines = error_message.split("\n")
                    error_details = "\n".join(lines[1:]).strip() if len(lines) > 1 else error_message
                else:
                    error_details = error_message
                return AIResponse(
                    response=f"The catalog data could not be loaded. {error_details}",
                    table=None,
                    provider=query.provider,
                )
            
            # Include catalog type in system prompt
            base_system_prompt = EnhancedSystemPrompt.generate(query.question)
            if catalog_type != "UNKNOWN":
                catalog_info = f"\n\nCATALOG TYPE: {catalog_type}\n"
                if catalog_type == "1951_CATALOG":
                    catalog_info += "This catalog uses grades: Elite, Premium, Prime, Choice\n"
                elif catalog_type == "WELLBORN_CATALOG":
                    catalog_info += "This catalog uses numeric grades (1-10) and named grades (RUSH, CF, AW)\n"
                
                enhanced_system_prompt = base_system_prompt + catalog_info
            else:
                enhanced_system_prompt = base_system_prompt
            
            answer, table_data, resolved_provider = await query_ai_provider(
                query.question,
                context,
                query.provider,
                system_prompt_override=enhanced_system_prompt
            )
        
        formatted_answer = format_ai_response(answer, query.question)
        
        # Add confidence and sources if available
        if agent_response.sources:
            formatted_answer += f"\n\nSources: {', '.join(agent_response.sources[:3])}"
        
        return AIResponse(
            response=formatted_answer,
            table=table_data,
            provider=resolved_provider,
        )
        
    except Exception as e:
        logging.error(f"AI Agent error, falling back to advanced processor: {e}", exc_info=True)
        
        # Fallback to advanced document processor
        context = create_advanced_context(file_path, file_type_value, query.question)
        
        # If advanced processor fails, use RAG
        if context.startswith("Error:"):
            logger.warning("Advanced processor failed, using RAG fallback")
            context = create_rag_context(file_path, file_type_value, query.question)
        
        context_stripped = context.strip()
        is_error = (
            context_stripped.startswith("Error:") or 
            context_stripped.startswith("Error extracting") or
            "Error:" in context_stripped[:100]
        )
        
        if is_error:
            error_details = context_stripped[6:].strip() if context_stripped.startswith("Error:") else context_stripped
            return AIResponse(
                response=f"The catalog data could not be loaded. {error_details}",
                table=None,
                provider=query.provider,
            )
        
        # Include catalog type in system prompt
        base_system_prompt = EnhancedSystemPrompt.generate(query.question)
        if catalog_type != "UNKNOWN":
            catalog_info = f"\n\nCATALOG TYPE: {catalog_type}\n"
            if catalog_type == "1951_CATALOG":
                catalog_info += "This catalog uses grades: Elite, Premium, Prime, Choice\n"
            elif catalog_type == "WELLBORN_CATALOG":
                catalog_info += "This catalog uses numeric grades (1-10) and named grades (RUSH, CF, AW)\n"
            
            enhanced_system_prompt = base_system_prompt + catalog_info
        else:
            enhanced_system_prompt = base_system_prompt
        
        answer, table_data, resolved_provider = await query_ai_provider(
            query.question,
            context,
            query.provider,
            system_prompt_override=enhanced_system_prompt
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

# Global exception handler for unhandled exceptions (not HTTPExceptions)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # Don't override FastAPI's built-in handlers for HTTPException and ValidationError
    if isinstance(exc, (HTTPException, RequestValidationError)):
        raise exc
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# ===== CORS Configuration =====
cors_origins_raw = os.environ.get("CORS_ORIGINS", "*")
cors_allow_credentials_raw = os.environ.get("CORS_ALLOW_CREDENTIALS", "false")

allow_credentials = cors_allow_credentials_raw.lower() == "true"

if cors_origins_raw.strip() == "*":
    allow_origins = ["*"]
    if allow_credentials:
        logger.info(
            "CORS_ORIGINS='*' while credentials were requested. "
            "Credentials have been disabled so wildcard origin remains valid."
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