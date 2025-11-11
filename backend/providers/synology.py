import httpx
import os
from typing import List, Optional
from .base import FileSystemProvider, FileItem

# Synology API의 응답 형식에 맞춘 Pydantic 모델 (필요에 따라 추가)

class SynologyAPIProvider(FileSystemProvider):
    """
    Synology File Station API를 위한 Provider.
    """
    def __init__(self, host: str, port: str, username: str, password: str, secure: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.secure = secure

        self.base_url = f"https://{self.host}:{self.port}/webapi" if self.secure else f"http://{self.host}:{self.port}/webapi"
        self._sid = None # 세션 ID
        self._syno_token = None # CSRF 방지를 위한 Syno Token
        self.client = httpx.AsyncClient(verify=self.secure) # 비동기 HTTP 클라이언트

    async def _login(self, otp_code: Optional[str] = None):
        """
        Synology NAS에 로그인하여 세션 ID (_sid)를 얻습니다.
        2FA를 위해 otp_code를 선택적으로 받습니다.
        """
        api_path = "entry.cgi"
        params = {
            "api": "SYNO.API.Auth",
            "version": "7", # 최신 버전에 따라 조절
            "method": "login",
            "account": self.username,
            "passwd": self.password,
            "session": "FileStation",
            "format": "sid"
        }
        # 2FA 코드가 제공된 경우, 파라미터에 추가
        if otp_code:
            params["otp_code"] = otp_code

        try:
            # POST 요청 시에는 파라미터를 'data'로 전달하여 form-encoded body로 보냅니다.
            response = await self.client.post(f"{self.base_url}/{api_path}", data=params)
            response.raise_for_status() # HTTP 오류 발생 시 예외 발생
            data = response.json()

            if data.get("success"):
                self._sid = data["data"]["sid"]
                self._syno_token = data["data"].get("synotoken") # synotoken 가져오기
                print(f"Synology NAS 로그인 성공. SID: {self._sid}")
                
                # CSRF 토큰이 있는 경우, 클라이언트의 기본 헤더로 설정
                if self._syno_token:
                    self.client.headers["X-SYNO-Token"] = self._syno_token
                    print(f"Syno-Token 설정 완료.")
            else:
                # API 레벨에서 로그인 실패 처리
                error_code = data.get("error", {}).get("code")
                raise ConnectionRefusedError(f"Synology 로그인 실패. 오류 코드: {error_code}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Synology NAS에 연결할 수 없습니다: {e}")

    async def list_shares(self) -> List[FileItem]:
        """
        Synology NAS의 모든 공유 폴더 목록을 조회합니다.
        """
        if not self._sid:
            await self._login()

        api_path = "entry.cgi"
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list_share",
            "_sid": self._sid,
        }

        try:
            response = await self.client.get(f"{self.base_url}/{api_path}", params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                error_code = data.get("error", {}).get("code")
                raise PermissionError(f"공유 폴더 목록 조회 실패. 오류 코드: {error_code}")

            items = []
            for share_data in data["data"]["shares"]:
                item = FileItem(
                    name=share_data["name"],
                    is_directory=True,
                    path=share_data["path"],
                    size=None,
                    last_modified=0 # 공유 폴더는 수정 시간이 없음
                )
                items.append(item)
            
            return items
        except httpx.RequestError as e:
            raise ConnectionError(f"Synology NAS API 요청 실패: {e}")

    async def list_files(self, path: str) -> List[FileItem]:
        """
        지정된 경로의 파일 및 디렉터리 목록을 반환합니다.
        """
        if not self._sid:
            # 이 흐름은 로그인 페이지를 사용하는 정상적인 시나리오에서는 발생하지 않아야 합니다.
            raise PermissionError("Not logged in. Please authenticate via /api/login first.")

        api_path = "entry.cgi"
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "_sid": self._sid, # URL 파라미터로 SID 명시적 전달
            "folder_path": path,
            "additional": '["real_path","size","owner","time"]' # 추가 정보 요청
        }
        
        try:
            # GET 요청 시에는 파라미터를 'params'로 전달합니다.
            # 클라이언트에 설정된 기본 헤더(X-SYNO-Token)와 쿠키는 자동으로 포함됩니다.
            response = await self.client.get(f"{self.base_url}/{api_path}", params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                error_code = data.get("error", {}).get("code")
                # 재로그인 로직 대신, 명확한 에러를 발생시켜 프론트엔드가 처리하도록 함
                raise PermissionError(f"파일 목록 조회 실패. 오류 코드: {error_code}")

            items = []
            for file_data in data["data"]["files"]:
                is_dir = file_data["isdir"]
                item = FileItem(
                    name=file_data["name"],
                    is_directory=is_dir,
                    path=file_data["path"],
                    size=file_data["additional"]["size"] if not is_dir else None,
                    last_modified=file_data["additional"]["time"]["mtime"]
                )
                items.append(item)
            
            return items
        except httpx.RequestError as e:
            raise ConnectionError(f"Synology NAS API 요청 실패: {e}")

    async def close(self):
        """
        HTTP 클라이언트 세션을 닫습니다.
        """
        await self.client.aclose()
