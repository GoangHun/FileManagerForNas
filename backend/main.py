import os
import uuid
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
from pathlib import Path

# Provider 관련 모듈 import
from .providers.base import FileSystemProvider
from .providers.local import LocalProvider
from .providers.synology import SynologyAPIProvider
from .search_service import SearchService # SearchService 임포트

# --- Pydantic 모델 정의 ---
class LoginRequest(BaseModel):
    host: str
    port: int = 5001
    username: str
    password: str
    secure: bool = True
    otp_code: Optional[str] = None # 2FA 코드를 위한 선택적 필드

# --- FastAPI 앱 설정 ---
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # 세션과 Provider 인스턴스를 저장할 딕셔너리
    app.state.sessions: Dict[str, FileSystemProvider] = {}
    # 인증되지 않은 사용자를 위한 기본 Provider
    app.state.default_provider = LocalProvider()
    # AI 검색 서비스를 초기화합니다.
    app.state.search_service = SearchService()

@app.on_event("shutdown")
async def shutdown_event():
    # 모든 활성 Provider 세션의 리소스를 정리
    for provider in app.state.sessions.values():
        if hasattr(provider, 'close'):
            await provider.close()
    # ChromaDB 클라이언트가 데이터를 디스크에 저장하도록 합니다.
    if app.state.search_service.client:
        app.state.search_service.client.persist()
        print("ChromaDB persisted to disk during shutdown.")

# CORS 미들웨어 추가
origins = [
    "http://localhost",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 의존성 주입 ---
async def get_provider(
    req: Request,
    authorization: Optional[str] = Header(None)
) -> FileSystemProvider:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        provider = req.app.state.sessions.get(token)
        if provider:
            return provider
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return req.app.state.default_provider

# --- API 엔드포인트 ---
@app.get("/")
def read_root():
    return {"message": "Welcome to AI File Management Backend!"}

@app.post("/api/login")
async def login(login_data: LoginRequest):
    """
    Synology NAS 접속 정보를 받아 로그인을 시도하고 세션 토큰을 발급합니다.
    """
    try:
        provider = SynologyAPIProvider(
            host=login_data.host,
            port=str(login_data.port),
            username=login_data.username,
            password=login_data.password,
            secure=login_data.secure
        )
        await provider._login(otp_code=login_data.otp_code)
        
        session_token = str(uuid.uuid4())
        app.state.sessions[session_token] = provider
        
        return {"token": session_token, "message": "Login successful"}
    except (ConnectionRefusedError, ConnectionError) as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.get("/api/files")
async def list_files(path: str = ".", provider: FileSystemProvider = Depends(get_provider)):
    """
    지정된 경로의 파일 및 디렉터리 목록을 반환합니다.
    루트 경로('/') 요청 시 공유 폴더 목록을 반환합니다.
    """
    try:
        if isinstance(provider, SynologyAPIProvider) and path in ('/', '.'):
            items = await provider.list_shares()
        else:
            items = await provider.list_files(path)
        return {"path": path, "items": items}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

@app.get("/api/search")
async def search_files(query: str, req: Request, n_results: int = 5):
    """
    AI 기반 스마트 검색을 수행하여 파일 내용을 기반으로 유사한 파일을 찾습니다.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    results = await req.app.state.search_service.search(query, n_results)
    return {"query": query, "results": results}

@app.post("/api/index_files")
async def index_files(req: Request, directory: str = "./"):
    """
    지정된 디렉토리의 텍스트 파일을 스캔하고 내용을 ChromaDB에 인덱싱합니다.
    (현재는 로컬 파일 시스템만 지원하며, 프로젝트 루트 내의 경로만 허용합니다.)
    """
    search_service: SearchService = req.app.state.search_service
    indexed_count = 0
    
    base_path = Path(os.getcwd())
    target_dir = (base_path / directory).resolve()

    if not target_dir.is_dir() or not target_dir.is_relative_to(base_path):
        raise HTTPException(status_code=400, detail="Invalid or unsafe directory path.")

    for root, _, files in os.walk(target_dir):
        for file_name in files:
            file_path = Path(root) / file_name
            # 텍스트 파일만 인덱싱합니다.
            if file_path.suffix in ['.txt', '.md', '.py', '.js', '.ts', '.json', '.csv']:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    await search_service.index_file(str(file_path.relative_to(base_path)), content)
                    indexed_count += 1
                except Exception as e:
                    print(f"Error indexing {file_path}: {e}")
    
    return {"message": f"Indexed {indexed_count} text files from {directory}", "indexed_files": search_service.get_indexed_files()}
