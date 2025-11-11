from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import List, Optional

# 프론트엔드의 FileItem 인터페이스와 일치하는 Pydantic 모델
# 모든 Provider는 이 형식에 맞춰 파일 정보를 반환해야 합니다.
class FileItem(BaseModel):
    name: str
    is_directory: bool
    path: str
    size: Optional[int] = None
    last_modified: float

# 모든 파일 시스템 Provider가 상속받아야 할 추상 기본 클래스(ABC)
class FileSystemProvider(ABC):
    """
    파일 시스템 Provider를 위한 추상 기본 클래스.
    모든 Provider는 이 클래스에 정의된 메서드들을 반드시 구현해야 합니다.
    """

    @abstractmethod
    async def list_files(self, path: str) -> List[FileItem]:
        """
        지정된 경로의 파일 및 디렉터리 목록을 비동기적으로 반환합니다.

        :param path: 조회할 경로
        :return: FileItem 모델의 리스트
        """
        pass

    # 향후 확장을 위해 주석 처리된 메서드들
    # @abstractmethod
    # async def get_file_info(self, path: str) -> FileItem:
    #     pass
    #
    # @abstractmethod
    # async def move_file(self, source: str, destination: str):
    #     pass
    #
    # @abstractmethod
    # async def delete_file(self, path: str):
    #     pass
    #
    # @abstractmethod
    # async def create_directory(self, path: str):
    #     pass
