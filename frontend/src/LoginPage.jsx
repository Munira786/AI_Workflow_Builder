import { useState } from 'react';
import { useAuth } from './AuthContext';

const MAX_PASSWORD_BYTES = 72; // bcrypt's limit, enforced by the backend too

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
    if (!isLogin && new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
      setError(`Password is too long (at most ${MAX_PASSWORD_BYTES} bytes).`);
      return;
    }
    setBusy(true);
    try {
      await (isLogin ? login(email, password) : register(email, password));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="centered centered--page">
      <form onSubmit={handleSubmit} className="card login">
        <h1 className="login__title">AI Workflow Builder</h1>
        <p className="text-muted">{isLogin ? 'Sign in to your account' : 'Create an account'}</p>

        <label className="field">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            autoComplete="email"
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            autoComplete={isLogin ? 'current-password' : 'new-password'}
          />
        </label>

        {error && <div role="alert" className="text-danger">{error}</div>}

        <button type="submit" disabled={busy} className="btn btn--primary">
          {busy ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
        </button>
        <button
          type="button"
          onClick={() => { setMode(isLogin ? 'register' : 'login'); setError(''); }}
          className="btn btn--ghost"
        >
          {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  );
};
