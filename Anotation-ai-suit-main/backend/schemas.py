from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}

# Project Schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

# File Schemas
class FileBase(BaseModel):
    name: str
    folder_id: Optional[int] = None

class FileCreate(FileBase):
    project_id: int

class FileResponse(FileBase):
    id: int
    file_path: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    project_id: int
    uploaded_at: datetime
    
    model_config = {"from_attributes": True}

# Annotation Schemas
class AnnotationBase(BaseModel):
    annotation_data: Any  # Accepts dict, list, or any JSON-serializable data

class AnnotationCreate(AnnotationBase):
    file_id: int

class AnnotationResponse(AnnotationBase):
    id: int
    file_id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

# Message Schemas
class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    project_id: int

class MessageResponse(MessageBase):
    id: int
    project_id: int
    user_id: int
    created_at: datetime
    user: UserResponse
    
    model_config = {"from_attributes": True}

# Pricing AI Schemas
class ChatMessage(BaseModel):
    message: str
    file_id: int

class ChatResponse(BaseModel):
    response: str
    model_used: str

# Token Schema
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# Folder Schemas
class FolderBase(BaseModel):
    name: str


class FolderCreate(FolderBase):
    pass


class FolderResponse(FolderBase):
    id: int
    project_id: int
    created_at: datetime
    model_config = {"from_attributes": True}

