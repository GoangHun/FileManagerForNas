import os
from typing import List
from .base import FileSystemProvider, FileItem

class LocalProvider(FileSystemProvider):
    """
    로컬 파일 시스템을 위한 Provider.
    로컬 디렉터리와 파일에 접근하여 정보를 가져옵니다.
    """
    def __init__(self, root_dir: str = None):
        # root_dir이 지정되지 않으면 현재 작업 디렉터리를 사용합니다.
        self.root_dir = os.path.abspath(root_dir) if root_dir else os.getcwd()

    async def list_files(self, path: str) -> List[FileItem]:
        """
        지정된 로컬 경로의 파일 및 디렉터리 목록을 비동기적으로 반환합니다.
        (실제 I/O는 동기적으로 동작하지만, 인터페이스와의 호환성을 위해 async로 선언)
        """
        try:
            # 요청된 경로와 루트 디렉터리를 결합하여 절대 경로를 만듭니다.
            full_path = os.path.abspath(os.path.join(self.root_dir, path))

            # 보안 검사: 최종 경로가 루트 디렉터리 내에 있는지 확인합니다.
            if not full_path.startswith(self.root_dir):
                raise PermissionError("Access denied: Path is outside the root directory.")

            if not os.path.exists(full_path) or not os.path.isdir(full_path):
                raise FileNotFoundError(f"Directory not found or path is not a directory: {path}")

            items = []
            for item_name in os.listdir(full_path):
                item_path = os.path.join(full_path, item_name)
                is_directory = os.path.isdir(item_path)
                
                # FileItem 모델에 맞춰 데이터 구성
                item = FileItem(
                    name=item_name,
                    is_directory=is_directory,
                    # 클라이언트가 사용할 상대 경로를 계산합니다.
                    path=os.path.relpath(item_path, self.root_dir).replace('\\', '/'),
                    size=os.path.getsize(item_path) if not is_directory else None,
                    last_modified=os.path.getmtime(item_path)
                )
                items.append(item)
            
            return items
        except (FileNotFoundError, PermissionError) as e:
            # 특정 예외는 그대로 다시 발생시켜 API 엔드포인트에서 처리하도록 합니다.
            raise e
        except Exception as e:
            # 그 외 예외는 일반적인 오류로 처리합니다.
            raise IOError(f"An unexpected error occurred while listing files: {e}")

