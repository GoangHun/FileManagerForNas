import os
from typing import List, Dict, Any
from chromadb import Client, Settings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

class SearchService:
    def __init__(self, db_path: str = "./chroma_db"):
        # ChromaDB 클라이언트 초기화
        # db_path에 데이터를 영구 저장합니다.
        self.client = Client(Settings(
            persist_directory=db_path,
            is_persistent=True
        ))
        
        # SentenceTransformer 모델 로드
        # 'BM-K/KoSimCSE-roberta'는 한국어 검색 관련성 향상을 위한 모델입니다.
        self.embedding_model = SentenceTransformer('BM-K/KoSimCSE-roberta')
        
        # ChromaDB 컬렉션 생성 또는 가져오기
        # embedding_function을 SentenceTransformer 모델로 설정합니다.
        self.collection = self.client.get_or_create_collection(
            name="file_contents",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name='BM-K/KoSimCSE-roberta')
        )
        print(f"ChromaDB initialized at {db_path} with collection 'file_contents'")

    async def index_chunks(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """
        여러 텍스트 청크를 임베딩하여 ChromaDB에 일괄 저장합니다.
        """
        if not documents:
            return
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Indexed {len(documents)} chunks.")

    async def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        쿼리를 기반으로 ChromaDB에서 유사한 파일을 검색하고, 결과의 다양성을 보장합니다.
        """
        item_count = self.collection.count()
        if item_count == 0:
            return []
        
        # 더 많은 후보군을 가져와서 다양성을 확보. n_results의 10배 또는 50개 중 더 작은 값으로 설정.
        candidate_n_results = min(n_results * 10, 50, item_count) 

        results = self.collection.query(
            query_texts=[query],
            n_results=candidate_n_results,
            include=['documents', 'metadatas', 'distances']
        )
        
        # 결과를 파싱하고 거리 기준으로 정렬
        parsed_results = []
        if results and results['metadatas'] and results['metadatas'][0]:
            for i in range(len(results['metadatas'][0])):
                metadata = results['metadatas'][0][i]
                parsed_results.append({
                    "file_path": metadata.get('file_path', 'Unknown'),
                    "content_snippet": results['documents'][0][i],
                    "distance": results['distances'][0][i],
                    "chunk_number": metadata.get('chunk_number', 0)
                })
        
        parsed_results.sort(key=lambda x: x['distance'])

        # 파일 경로 기준으로 중복을 제거하여 다양한 파일의 결과를 반환
        final_results = []
        seen_files = set()
        for result in parsed_results:
            if len(final_results) >= n_results:
                break
            if result['file_path'] not in seen_files:
                final_results.append(result)
                seen_files.add(result['file_path'])
                
        return final_results

    def get_indexed_files(self) -> List[str]:
        """
        현재 ChromaDB에 인덱싱된 파일 경로 목록을 반환합니다.
        """
        all_ids = self.collection.get(include=[])['ids']
        if not all_ids:
            return []

        results = self.collection.get(ids=all_ids, include=['metadatas'])
        
        unique_paths = set()
        if results['metadatas']:
            for metadata in results['metadatas']:
                if metadata and 'file_path' in metadata:
                    unique_paths.add(metadata['file_path'])
        return list(unique_paths)

    def delete_indexed_file(self, file_path: str):
        """
        ChromaDB에서 특정 파일의 인덱스를 삭제합니다. (이제 폴더 기반 삭제를 권장)
        """
        # 이 메서드는 이제 청크 기반 삭제가 필요하므로 delete_files_in_folder를 사용해야 합니다.
        self.delete_files_in_folder(file_path)

    async def delete_files_in_folder(self, folder_path: str) -> int:
        """
        ChromaDB에서 특정 폴더 경로 하위의 모든 파일 인덱스를 삭제합니다.
        """
        # ChromaDB는 metadata 필드에 대한 "starts with" 필터링을 직접 지원하지 않습니다.
        # 따라서 모든 ID를 가져와서 애플리케이션 레벨에서 필터링합니다.
        all_ids = self.collection.get(include=[])['ids']
        
        ids_to_delete = [
            doc_id for doc_id in all_ids if doc_id.startswith(folder_path)
        ]
        
        if not ids_to_delete:
            return 0
            
        self.collection.delete(ids=ids_to_delete)
        print(f"Deleted {len(ids_to_delete)} files from folder {folder_path}")
        return len(ids_to_delete)

    def reset_db(self):
        """
        ChromaDB를 완전히 초기화합니다 (모든 데이터 삭제).
        """
        self.client.delete_collection(name="file_contents")
        self.collection = self.client.get_or_create_collection(
            name="file_contents",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name='BM-K/KoSimCSE-roberta')
        )
        print("ChromaDB reset.")

    def __del__(self):
        # 애플리케이션 종료 시 ChromaDB 클라이언트가 데이터를 디스크에 저장하도록 합니다.
        # is_persistent=True 설정으로 자동 저장되므로 명시적 호출은 필요하지 않을 수 있습니다.
        if self.client:
            # self.client.persist() # Removed as it might not be needed with is_persistent=True
            print("ChromaDB client initialized with persistence.")
