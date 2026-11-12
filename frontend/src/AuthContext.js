// AuthContext.js
// Holds the logged-in user and exposes login / register / logout.

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, onUnauthorized, tokenStorage } from './api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => tokenStorage.get());
  const [user, setUser] = useState(null);

  const logout = useCallback(() => {
    tokenStorage.set(null);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    onUnauthorized(logout);
  }, [logout]);

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
