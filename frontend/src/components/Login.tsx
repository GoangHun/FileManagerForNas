import React, { useState, useEffect } from 'react';
import './Login.css';

// Login 컴포넌트의 props 타입을 정의합니다.
interface LoginProps {
  onLogin: (credentials: any) => Promise<void>;
  error: string | null;
}

const Login: React.FC<LoginProps> = ({ onLogin, error }) => {
  // 폼 입력 값을 위한 상태
  const [host, setHost] = useState('');
  const [port, setPort] = useState('5001');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [secure, setSecure] = useState(true); // HTTPS 사용 여부 상태
  const [otpCode, setOtpCode] = useState(''); // 2FA(OTP) 코드 상태
  const [isLoading, setIsLoading] = useState(false);

  // secure 상태 변경에 따라 port 기본값 변경
  useEffect(() => {
    if (secure && port === '5000') {
      setPort('5001');
    } else if (!secure && port === '5001') {
      setPort('5000');
    }
  }, [secure, port]); // port도 의존성 배열에 추가하여 현재 port 값에 따라 동작하도록 함

  // 폼 제출 시 실행될 핸들러
  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    await onLogin({
      host,
      port: parseInt(port, 10),
      username,
      password,
      secure,
      otp_code: otpCode, // otp_code 전달
    });
    setIsLoading(false);
  };

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit} className="login-form">
        <h2>Synology NAS Login</h2>
        
        {error && <p className="login-error">Error: {error}</p>}

        <div className="form-group">
          <label htmlFor="host">Host / IP Address</label>
          <input
            id="host"
            type="text"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="e.g., 192.168.1.100 or mynas.synology.me"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="port">Port</label>
          <input
            id="port"
            type="number"
            value={port}
            onChange={(e) => setPort(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="otpCode">2FA Code (if enabled)</label>
          <input
            id="otpCode"
            type="text"
            value={otpCode}
            onChange={(e) => setOtpCode(e.target.value)}
            placeholder="123456"
          />
        </div>
        <div className="form-group-checkbox">
          <input
            id="secure"
            type="checkbox"
            checked={secure}
            onChange={(e) => setSecure(e.target.checked)}
          />
          <label htmlFor="secure">Use HTTPS (SSL)</label>
        </div>
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
};

export default Login;
