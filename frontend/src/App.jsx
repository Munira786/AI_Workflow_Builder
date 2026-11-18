import { useEffect } from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import { ErrorBoundary } from './ErrorBoundary';
import { Header } from './Header';
import { LoginPage } from './LoginPage';
import { Toolbar } from './Toolbar';
import { Canvas } from './Canvas';
import { RunPanel } from './RunPanel';
import { RunHistory } from './RunHistory';
import { useStore } from './store';

const Editor = () => {
  const catalog = useStore((state) => state.catalog);
  const catalogError = useStore((state) => state.catalogError);
  const loadCatalog = useStore((state) => state.loadCatalog);

  useEffect(() => {
    if (!catalog) loadCatalog();
  }, [catalog, loadCatalog]);

  if (!catalog) {
    return (
      <div className="centered">
        {catalogError ? (
          <div role="alert" className="stack">
            <span className="text-danger">Could not load the editor: {catalogError}</span>
            <button type="button" className="btn btn--primary" onClick={loadCatalog}>
              Retry
            </button>
          </div>
        ) : (
          <span className="text-muted">Loading editor…</span>
        )}
      </div>
    );
  }

  return (
    <div>
      <Header />
      <Toolbar />
      <ErrorBoundary>
        <Canvas />
      </ErrorBoundary>
      <RunPanel />
      <ErrorBoundary>
        <RunHistory />
      </ErrorBoundary>
    </div>
  );
};

const Root = () => {
  const { token } = useAuth();
  return token ? <Editor /> : <LoginPage />;
};

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Root />
      </AuthProvider>
    </ErrorBoundary>
  );
}
