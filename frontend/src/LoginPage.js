// LoginPage.js

import { useState } from 'react';
import { useAuth } from './AuthContext';
import { buttonStyle, inputStyle } from './styles';

export const LoginPage = () => {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const isLogin = mode === 'login';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await (isLogin ? login(email, password) : register(email, password));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f8fafc' }}>
      <form
        onSubmit={handleSubmit}
        style={{
          width: 'min(360px, calc(100vw - 32px))',
          background: '#fff',
          padding: 28,
          borderRadius: 14,
          border: '1px solid #e5e7eb',
          boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22 }}>AI Workflow Builder</h1>
        <p style={{ margin: 0, color: '#6b7280' }}>{isLogin ? 'Sign in to your account' : 'Create an account'}</p>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} autoComplete="email" />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={inputStyle}
            autoComplete={isLogin ? 'current-password' : 'new-password'}
          />
        </label>

        {error && <div role="alert" style={{ color: '#b91c1c', fontSize: 14 }}>{error}</div>}

        <button type="submit" disabled={busy} style={buttonStyle('primary')}>
          {busy ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
        </button>
        <button
          type="button"
          onClick={() => { setMode(isLogin ? 'register' : 'login'); setError(''); }}
          style={{ ...buttonStyle('ghost'), border: 'none' }}
        >
          {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  );
};
