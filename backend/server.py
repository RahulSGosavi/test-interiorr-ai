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
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt  # type: ignore
import json
import aiofiles
# Heavy libs imported lazily in handlers to keep baseline RAM low

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

# Pricing AI integration with LiteLLM
try:
    import litellm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    # Logger will be initialized later, warning will be printed after logger setup

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

# Warn about missing LLM package if not available
if not LLM_AVAILABLE:
    logger.warning("emergentintegrations not available. Pricing AI features will be disabled.")

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
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
            user.hashed_password = get_password_hash(credentials.password)
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
            file_path = Path(file_obj.file_path)
            if not file_path.is_absolute():
                file_path = UPLOAD_DIR / file_obj.file_path
            
            if os.path.exists(file_path):
                os.remove(file_path)
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
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete associated files (and physical files)
    files = db.query(DBFile).filter(DBFile.folder_id == folder_id).all()
    for file_obj in files:
        try:
            if os.path.exists(file_obj.file_path):
                os.remove(file_obj.file_path)
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
    file_type = None
    if file.filename.lower().endswith('.pdf'):
        file_type = "pdf"
    elif file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        file_type = "excel"

    file_ext = Path(file.filename).suffix
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
        name=file.filename,
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
    file_path = Path(db_file.file_path)
    if not file_path.is_absolute():
        file_path = UPLOAD_DIR / db_file.file_path
    
    print(f"[DEBUG] Attempting to download file: {file_path}")
    print(f"[DEBUG] UPLOAD_DIR: {UPLOAD_DIR}")
    print(f"[DEBUG] File exists: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
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
    
    return FastAPIFileResponse(
        path=str(file_path),
        filename=db_file.name,
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
    if folder_id is not None:
        folder_ref = db.query(Folder).filter(Folder.id == folder_id, Folder.project_id == project_id).first()
        if not folder_ref:
            raise HTTPException(status_code=404, detail="Folder not found")

    db_file = await _save_uploaded_file(file, project_id, db, folder_id=folder_ref.id if folder_ref else None)
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

    project = db.query(Project).filter(Project.id == folder.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    db_file = await _save_uploaded_file(file, folder.project_id, db, folder_id=folder_id)
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

    project = db.query(Project).filter(Project.id == folder.project_id).first()
    if not project or project.owner_id != current_user.id:
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
    if project.owner_id != current_user.id:
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
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete physical file
    try:
        # Resolve file path (handle both old absolute paths and new relative paths)
        file_path = Path(db_file.file_path)
        if not file_path.is_absolute():
            file_path = UPLOAD_DIR / db_file.file_path
        
        if os.path.exists(file_path):
            os.remove(file_path)
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
    if project.owner_id != current_user.id:
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
        existing.annotation_data = annotation_dict
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
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    annotations = db.query(Annotation).filter(Annotation.file_id == file_id).all()
    return [AnnotationResponse.model_validate(a) for a in annotations]

# ===== Pricing AI Helper Functions =====
def extract_file_content(file_path: Path, file_type: str) -> str:
    """Extract text content from various file types"""
    try:
        if file_type == 'pdf':
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        
        elif file_type in ['xlsx', 'xls']:
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

async def query_ai_provider(question: str, context: str, provider: str = "gemini") -> tuple[str, Optional[List[Dict[str, Any]]]]:
    """Query AI provider with context"""
    if not LLM_AVAILABLE:
        return "AI integration is not available. Please install litellm.", None
    
    try:
        # Prepare the prompt
        system_prompt = """You are a helpful AI assistant specialized in analyzing pricing documents, 
spreadsheets, and CAD/construction documents. You can extract information, perform calculations, 
and answer questions about costs, quantities, codes, and other data in the documents.

When presenting tabular data, format your response with the data clearly visible as text, 
and I will extract it into a proper table format."""

        user_prompt = f"""Document Content:
{context[:15000]}  

Question: {question}

Please provide a clear and concise answer. If the answer involves tabular data, 
present it in a structured format."""

        # Map provider names
        model_name = "gemini/gemini-2.0-flash-exp" if provider == "gemini" else "gpt-4o-mini"
        
        # Query using litellm
        import litellm
        litellm.set_verbose = False
        
        response = litellm.completion(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        answer = response.choices[0].message.content
        
        # Try to extract table data if present
        table_data = None
        # Simple table detection (can be enhanced)
        if '|' in answer or '\t' in answer:
            try:
                # Attempt to parse table-like content
                lines = answer.split('\n')
                table_lines = [line for line in lines if '|' in line or '\t' in line]
                if len(table_lines) > 1:
                    # Basic table parsing
                    import pandas as pd
                    # This is a simplified parser, real implementation would be more robust
                    pass  # Table extraction can be enhanced
            except:
                pass
        
        return answer, table_data
    
    except Exception as e:
        logging.error(f"AI query error: {e}")
        error_msg = str(e)
        if "API key" in error_msg or "authentication" in error_msg.lower():
            return f"AI provider authentication error. Please configure API keys in environment variables.", None
        return f"Error querying AI: {str(e)}", None

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
    file_path = Path(db_file.file_path)
    if not file_path.is_absolute():
        file_path = UPLOAD_DIR / db_file.file_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path}")
    
    # Extract file content
    content = extract_file_content(file_path, db_file.file_type)
    
    if not content or "Error" in content:
        raise HTTPException(status_code=400, detail=content)
    
    # Query AI
    answer, table_data = await query_ai_provider(query.question, content, query.provider)
    
    return AIResponse(
        response=answer,
        table=table_data,
        provider=query.provider
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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
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