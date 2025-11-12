// TypeScript의 인터페이스를 사용하여 파일/디렉터리 아이템 객체의 구조(shape)를 정의합니다.
// 이를 통해 API로부터 받은 데이터의 형식을 강제하고, 개발 중 발생할 수 있는 타입 관련 버그를 예방합니다.
export interface FileItem {
  name: string;
  is_directory: boolean;
  path: string;
  size: number | null;
  last_modified: number;
}

export interface SearchResult {
  file_path: string;
  content_snippet: string;
  distance: number;
  chunk_number: number; // Add this line
}

export type FolderStatus = 'indexed' | 'not_indexed' | 'outdated' | 'indexing' | 'failed';

export type FolderStatusMap = {
  [path: string]: FolderStatus;
};
