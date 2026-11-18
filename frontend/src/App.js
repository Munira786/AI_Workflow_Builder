import { AuthProvider, useAuth } from './AuthContext';
import { Header } from './Header';
import { LoginPage } from './LoginPage';
import { PipelineToolbar } from './toolbar';
import { PipelineUI } from './ui';
import { RunPanel } from './RunPanel';

const Editor = () => (
  <div>
    <Header />
    <PipelineToolbar />
    <PipelineUI />
    <RunPanel />
  </div>
);

const Root = () => {
  const { token } = useAuth();
  return token ? <Editor /> : <LoginPage />;
};

function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}

export default App;
