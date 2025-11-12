# 자연어 검색 기능 구현 상세

본 문서는 AI 파일 관리 시스템의 핵심 기능인 자연어 검색의 구현 세부 사항을 다룹니다. 사용자가 자연어 쿼리를 통해 파일을 검색할 수 있도록 하는 기술 스택, 데이터 흐름 및 주요 로직을 설명합니다.

## 1. 개요

자연어 검색 기능은 사용자가 일상적인 언어로 파일 내용을 검색할 수 있도록 하여, 기존의 키워드 기반 검색의 한계를 넘어섭니다. 이는 파일의 의미론적 내용을 이해하고, 쿼리와 의미적으로 유사한 파일을 찾아내는 방식으로 동작합니다.

## 2. 핵심 기술 스택

*   **임베딩 라이브러리:** `sentence-transformers` (Python)
    *   텍스트(문장, 문단)를 고차원 벡터(임베딩)로 변환하는 데 사용됩니다.
*   **임베딩 모델:** `BM-K/KoSimCSE-roberta`
    *   한국어 문장 임베딩에 특화된 사전 학습 모델로, 높은 정확도로 한국어 텍스트의 의미적 유사성을 포착합니다.
*   **벡터 데이터베이스:** `ChromaDB` (Python)
    *   생성된 텍스트 임베딩을 저장하고, 고속 유사도 검색(k-NN)을 수행하는 데 사용됩니다.
*   **백엔드 프레임워크:** `FastAPI` (Python)
    *   검색 및 인덱싱 관련 API 엔드포인트를 제공합니다.
*   **프론트엔드:** `React`, `TypeScript`
    *   사용자 인터페이스를 통해 검색 쿼리를 입력받고 결과를 표시합니다.

## 3. 구현 세부 사항

### 3.1. 텍스트 청킹 (Text Chunking)

파일의 내용을 효과적으로 임베딩하고 검색하기 위해, 긴 텍스트 문서는 작은 단위의 '청크(chunk)'로 분할됩니다.

*   **목적:**
    *   임베딩 모델의 입력 길이 제한을 준수합니다.
    *   특정 문맥에 대한 검색 정확도를 높입니다.
    *   검색 결과 스니펫의 가독성을 향상시킵니다.
*   **구현:** `backend/main.py`의 `chunk_text` 헬퍼 함수에서 처리됩니다.
    *   `chunk_size`: 각 청크의 최대 길이 (기본값: 500자).
    *   `chunk_overlap`: 청크 간의 중첩 길이 (기본값: 50자). 중첩을 통해 문맥 손실을 최소화합니다.

### 3.2. 임베딩 생성 (Embedding Generation)

분할된 텍스트 청크는 `BM-K/KoSimCSE-roberta` 모델을 사용하여 고차원 벡터로 변환됩니다.

*   **라이브러리:** `sentence_transformers.SentenceTransformer`
*   **모델:** `BM-K/KoSimCSE-roberta`
*   **구현:** `backend/search_service.py`의 `SearchService` 클래스 초기화 시 모델이 로드되며, `index_chunks` 메서드에서 청크들을 임베딩합니다.

### 3.3. ChromaDB 상호작용

생성된 임베딩 벡터와 해당 메타데이터(파일 경로, 청크 번호 등)는 `ChromaDB`에 저장됩니다.

*   **데이터 저장:**
    *   `documents`: 텍스트 청크 내용.
    *   `metadatas`: `{ "file_path": "...", "chunk_number": N }` 형식의 메타데이터.
    *   `ids`: 각 청크의 고유 ID (예: `"{file_path}-chunk-{chunk_number}"`).
*   **구현:** `backend/search_service.py`의 `index_chunks` 메서드에서 `self.collection.add()`를 통해 데이터를 추가합니다.
*   **영속성:** `ChromaDB`는 `persist_directory` 설정(`./chroma_db`)을 통해 데이터를 디스크에 영구적으로 저장합니다.

### 3.4. 검색 로직 (`backend/search_service.py`)

사용자의 쿼리는 다음 단계를 거쳐 처리됩니다.

1.  **쿼리 임베딩:** 사용자 쿼리는 `BM-K/KoSimCSE-roberta` 모델을 통해 벡터로 변환됩니다.
2.  **ChromaDB 쿼리:** 쿼리 벡터를 사용하여 `ChromaDB`에서 의미적으로 가장 유사한 `candidate_n_results` (기본 50개)개의 청크를 검색합니다.
3.  **결과 정렬:** 검색된 청크들은 유사도 거리(distance)를 기준으로 오름차순 정렬됩니다.
4.  **파일 단위 중복 제거:** `n_results` (기본 5개)개의 고유한 파일에서 가장 유사한 청크를 선택하여 최종 결과 목록을 구성합니다. 이는 `seen_files` 집합을 사용하여 동일 파일의 중복 청크를 제거하고, 다양한 파일의 결과를 반환하도록 보장합니다.

### 3.5. API 엔드포인트 (`backend/main.py`)

*   **`GET /api/search?query={query}&n_results={n}`:**
    *   사용자 쿼리를 받아 `SearchService`를 통해 검색을 수행하고, 결과를 반환합니다.
*   **`POST /api/index/folder`:**
    *   특정 폴더의 파일을 백그라운드에서 청킹하고 임베딩하여 `ChromaDB`에 인덱싱합니다.
*   **`DELETE /api/index/folder`:**
    *   `ChromaDB`에서 특정 폴더와 관련된 모든 인덱스 데이터를 삭제합니다.
*   **`GET /api/debug/indexed-files`:**
    *   디버깅 목적으로 현재 `ChromaDB`에 인덱싱된 모든 파일 경로 목록을 반환합니다.
*   **`POST /api/debug/reset-db`:**
    *   디버깅 목적으로 `ChromaDB` 컬렉션을 완전히 초기화합니다.

### 3.6. 프론트엔드 통합 (`frontend/src/App.tsx`, `frontend/src/components/SearchResults.tsx`)

*   **`App.tsx`:**
    *   `handleSearch` 함수를 통해 백엔드의 `/api/search` 엔드포인트를 호출합니다.
    *   검색 결과를 `searchResults` 상태에 저장하고, `viewMode`를 'search'로 전환하여 `SearchResults` 컴포넌트를 렌더링합니다.
*   **`SearchResults.tsx`:**
    *   `searchResults` prop을 받아 검색 결과를 목록 형태로 표시합니다.
    *   각 결과 항목은 파일 경로, 내용 스니펫, 유사도 점수를 포함합니다.
    *   `key` prop은 `result.file_path`와 `result.chunk_number`를 조합하여 고유성을 보장합니다.

## 4. 문제 해결 및 개선 이력

*   **초기 문제:** 검색 시 단일 파일의 결과만 표시되는 문제.
    *   **해결:** `search_service.py`에서 `ChromaDB` 쿼리 시 `candidate_n_results`를 늘려 더 많은 후보군을 가져오고, 파일 단위 중복 제거 로직을 통해 다양한 파일의 결과를 보장하도록 개선.
*   **초기 문제:** 한국어 검색 관련성 부족.
    *   **해결:** 임베딩 모델을 `paraphrase-multilingual-MiniLM-L12-v2`에서 한국어에 특화된 `BM-K/KoSimCSE-roberta`로 변경하여 관련성 향상.
*   **초기 문제:** `ChromaDB` `persist()` 관련 `AttributeError` 및 모델 로딩 실패.
    *   **해결:** `SearchService.__del__`에서 불필요한 `self.client.persist()` 호출 제거. `BM-K/KoSimCSE-roberta` 모델이 `sentence-transformers`와 호환되도록 수정.

---
**참고:** 임베딩 모델 변경 시에는 반드시 `ChromaDB`를 초기화하고 모든 파일을 재인덱싱해야 합니다.
