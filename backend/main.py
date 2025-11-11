import os
import uuid
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict

# Provider 관련 모듈 import
from .providers.base import FileSystemProvider
from .providers.local import LocalProvider
from .providers.synology import SynologyAPIProvider

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

@app.on_event("shutdown")
async def shutdown_event():
    # 모든 활성 Provider 세션의 리소스를 정리
    for provider in app.state.sessions.values():
        if hasattr(provider, 'close'):
            await provider.close()

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
    req: Request, # 'request: object'를 'req: Request'로 변경
    authorization: Optional[str] = Header(None)
) -> FileSystemProvider:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        provider = req.app.state.sessions.get(token) # 'request'를 'req'로 변경
        if provider:
            return provider
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    # 인증 헤더가 없는 경우 기본 Provider 반환
    return req.app.state.default_provider # 'request'를 'req'로 변경

# --- API 엔드포인트 ---
@app.get("/")
def read_root():
    return {"message": "Welcome to AI File Management Backend!"}

@app.post("/api/login")
async def login(login_data: LoginRequest): # 'request'를 'login_data'로 변경
    """
    Synology NAS 접속 정보를 받아 로그인을 시도하고 세션 토큰을 발급합니다.
    """
    try:
        # 제공된 정보로 SynologyAPIProvider 인스턴스 생성
        provider = SynologyAPIProvider(
            host=login_data.host, # 'request.host'를 'login_data.host'로 변경
            port=str(login_data.port), # 'request.port'를 'login_data.port'로 변경
            username=login_data.username, # 'request.username'을 'login_data.username'으로 변경
            password=login_data.password, # 'request.password'를 'login_data.password'로 변경
            secure=login_data.secure # 'request.secure'를 'login_data.secure'로 변경
        )
        # 실제로 로그인을 시도하여 자격 증명 확인
        # otp_code는 provider의 _login 메서드에서 처리
        await provider._login(otp_code=login_data.otp_code) # 'request.otp_code'를 'login_data.otp_code'로 변경
        
        # 로그인 성공 시, 세션 토큰을 생성하고 Provider 인스턴스를 저장
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
        # Synology Provider이고 루트 경로가 요청된 경우, 공유 폴더 목록을 조회
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
