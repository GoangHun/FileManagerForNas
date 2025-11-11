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
        # 'all-MiniLM-L6-v2'는 작고 빠르며 좋은 성능을 보이는 영어 모델입니다.
        # 한국어 모델이 필요하다면 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2' 등을 고려할 수 있습니다.
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # ChromaDB 컬렉션 생성 또는 가져오기
        # embedding_function을 SentenceTransformer 모델로 설정합니다.
        self.collection = self.client.get_or_create_collection(
            name="file_contents",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name='all-MiniLM-L6-v2')
        )
        print(f"ChromaDB initialized at {db_path} with collection 'file_contents'")

    async def index_file(self, file_path: str, content: str):
        """
        파일 내용을 임베딩하여 ChromaDB에 저장합니다.
        """
        # ChromaDB는 자동으로 임베딩을 생성하므로, 여기서는 직접 임베딩하지 않습니다.
        # self.collection.add() 메서드에 content를 전달하면 embedding_function이 처리합니다.
        self.collection.add(
            documents=[content],
            metadatas=[{"file_path": file_path}],
            ids=[file_path] # 파일 경로를 ID로 사용하여 중복 방지 및 조회 용이
        )
        print(f"Indexed file: {file_path}")

    async def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        쿼리를 기반으로 ChromaDB에서 유사한 파일을 검색합니다.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        
        # 결과를 파싱하여 필요한 정보만 반환합니다.
        parsed_results = []
        if results and results['metadatas'] and results['metadatas'][0]:
            for i in range(len(results['metadatas'][0])):
                parsed_results.append({
                    "file_path": results['metadatas'][0][i]['file_path'],
                    "content_snippet": results['documents'][0][i][:200] + "..." if results['documents'][0][i] else "", # 내용 스니펫
                    "distance": results['distances'][0][i]
                })
        return parsed_results

    def get_indexed_files(self) -> List[str]:
        """
        현재 ChromaDB에 인덱싱된 파일 경로 목록을 반환합니다.
        """
        results = self.collection.get(
            ids=self.collection.get()['ids'], # 모든 ID를 가져옴
            include=['metadatas']
        )
        return [metadata['file_path'] for metadata in results['metadatas']] if results['metadatas'] else []

    def delete_indexed_file(self, file_path: str):
        """
        ChromaDB에서 특정 파일의 인덱스를 삭제합니다.
        """
        self.collection.delete(ids=[file_path])
        print(f"Deleted index for file: {file_path}")

    def reset_db(self):
        """
        ChromaDB를 완전히 초기화합니다 (모든 데이터 삭제).
        """
        self.client.delete_collection(name="file_contents")
        self.collection = self.client.get_or_create_collection(
            name="file_contents",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name='all-MiniLM-L6-v2')
        )
        print("ChromaDB reset.")

    def __del__(self):
        # 애플리케이션 종료 시 ChromaDB 클라이언트가 데이터를 디스크에 저장하도록 합니다.
        if self.client:
            self.client.persist()
            print("ChromaDB persisted to disk.")
