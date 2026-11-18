// Holds the logged-in user and exposes login / register / logout.

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, onUnauthorized, tokenStorage } from './api';
import { useStore } from './store';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => tokenStorage.get());
  const [user, setUser] = useState(null);

  const clearSession = useCallback(() => {
    tokenStorage.set(null);
    setToken(null);
    setUser(null);
    useStore.getState().resetSession();
  }, []);

  const logout = useCallback(async () => {
    // Revoke the token server-side (all devices); clear locally even if that call fails.
    await api('/auth/logout', { method: 'POST' }).catch(() => {});
    clearSession();
  }, [clearSession]);

  useEffect(() => {
    onUnauthorized(clearSession);
  }, [clearSession]);

  useEffect(() => {
    if (!token) return;
    api('/auth/me').then(setUser).catch(() => {});
  }, [token]);

  const saveToken = (data) => {
    tokenStorage.set(data.access_token);
    setToken(data.access_token);
  };

  const login = async (email, password) => {
    saveToken(await api('/auth/login', { method: 'POST', form: { username: email, password } }));
  };

  const register = async (email, password) => {
    saveToken(await api('/auth/register', { method: 'POST', body: { email, password } }));
  };

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
