// 1. Import (모듈 가져오기)
import React, { useState, useEffect } from 'react';
import './App.css';
import { FileItem as FileItemType } from './types';
import Header from './components/Header';
import PathNavigator from './components/PathNavigator';
import FileList from './components/FileList';
import Login from './components/Login';

// --- Helper Functions ---
const getErrorMessage = (err: any): string => {
  let errorMessage = 'An unknown error occurred.';
  
  // FastAPI 유효성 검사 에러 처리 (err.detail이 배열일 경우)
  if (err.detail && Array.isArray(err.detail) && err.detail[0]?.msg) {
    // 예: { loc: ["body", "username"], msg: "Field required" }
    errorMessage = err.detail.map((d: any) => 
      `${d.loc[d.loc.length - 1]}: ${d.msg}`
    ).join('; ');
  } 
  // 일반적인 FastAPI 에러 처리 (err.detail이 문자열일 경우)
  else if (err.detail && typeof err.detail === 'string') {
    errorMessage = err.detail;
  } 
  // 그 외 일반적인 JavaScript 에러 처리
  else if (err.message) {
    errorMessage = err.message;
  }
  
  return errorMessage;
};


// 2. Component (컴포넌트 정의)
function App() {
  // 3. State Management (상태 관리)
  const [files, setFiles] = useState<FileItemType[]>([]);
  const [currentPath, setCurrentPath] = useState<string>('/'); // Synology는 루트가 /
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  // 로그인 및 세션 상태
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  // 4. Side Effects & Data Fetching (사이드 이펙트와 데이터 요청)
  useEffect(() => {
    // 로그인 상태일 때만 파일 목록을 가져옵니다.
    if (!isLoggedIn || !sessionToken) return;

    const fetchFiles = async () => {
      setIsLoading(true);
      try {
        setError(null);
        const response = await fetch(`http://localhost:8000/api/files?path=${encodeURIComponent(currentPath)}`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        });
        if (!response.ok) {
          throw await response.json();
        }
        const data = await response.json();
        setFiles(data.items);
      } catch (err: any) {
        console.error('Error fetching files:', err);
        setError(getErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    };

    fetchFiles();
  }, [currentPath, isLoggedIn, sessionToken]);

  // 5. Event Handlers (이벤트 처리 함수)
  const handleLogin = async (credentials: any) => {
    try {
      setError(null);
      const response = await fetch('http://localhost:8000/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        throw await response.json();
      }

      const data = await response.json();
      setSessionToken(data.token);
      setIsLoggedIn(true);
    } catch (err: any)
    {
      console.error('Login failed:', err);
      setError(getErrorMessage(err));
    }
  };

  const handleItemClick = (item: FileItemType) => {
    if (item.is_directory) {
      setCurrentPath(item.path);
    }
  };

  const handleGoBack = () => {
    // 루트 디렉토리('/') 보다 더 뒤로 가지 않도록 처리
    if (currentPath === '/') return;
    const parentPath = currentPath.split('/').slice(0, -1).join('/') || '/';
    setCurrentPath(parentPath);
  };

  // 6. Rendering (UI 렌더링)
  if (!isLoggedIn) {
    return <Login onLogin={handleLogin} error={error} />;
  }

  return (
    <div className="App">
      <Header />
      <div className="file-explorer-container">
        {error && <p style={{ color: 'red' }}>Error: {error}</p>}
        
        {isLoading ? (
          <p>Loading files...</p>
        ) : (
          <>
            <PathNavigator 
              currentPath={currentPath} 
              onGoBack={handleGoBack} 
            />
            <FileList 
              files={files} 
              onItemClick={handleItemClick} 
            />
          </>
        )}
      </div>
    </div>
  );
}

export default App;
