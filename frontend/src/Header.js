// Header.js
// Pipeline name, save / open / new / delete, and the signed-in user.

import { useCallback, useEffect, useState } from 'react';
import { useStore } from './store';
import { shallow } from 'zustand/shallow';
import { api, serializeGraph } from './api';
import { useAuth } from './AuthContext';
import { buttonStyle, inputStyle } from './styles';

const selector = (state) => ({
  nodes: state.nodes,
  edges: state.edges,
  pipelineId: state.pipelineId,
  pipelineName: state.pipelineName,
  dirty: state.dirty,
  setPipelineName: state.setPipelineName,
  markSaved: state.markSaved,
  loadPipeline: state.loadPipeline,
  newPipeline: state.newPipeline,
});

export const Header = () => {
  const { user, logout } = useAuth();
  const {
    nodes, edges, pipelineId, pipelineName, dirty,
    setPipelineName, markSaved, loadPipeline, newPipeline,
  } = useStore(selector, shallow);

  const [pipelines, setPipelines] = useState([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const refreshList = useCallback(() => {
    api('/pipelines').then(setPipelines).catch((err) => setMessage(err.message));
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  const confirmDiscard = () => !dirty || window.confirm('Discard unsaved changes?');

  const withBusy = async (action) => {
    setBusy(true);
    setMessage('');
    try {
      await action();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  };

  const save = () =>
    withBusy(async () => {
      const body = { name: pipelineName.trim() || 'Untitled pipeline', graph: serializeGraph(nodes, edges) };
      const saved = pipelineId
        ? await api(`/pipelines/${pipelineId}`, { method: 'PATCH', body })
        : await api('/pipelines', { method: 'POST', body });
      markSaved(saved);
      setMessage('Saved');
      refreshList();
    });

  const open = (id) => {
    if (!id || !confirmDiscard()) return;
    withBusy(async () => loadPipeline(await api(`/pipelines/${id}`)));
  };

  const remove = () => {
    if (!pipelineId || !window.confirm(`Delete "${pipelineName}"? This cannot be undone.`)) return;
    withBusy(async () => {
      await api(`/pipelines/${pipelineId}`, { method: 'DELETE' });
      newPipeline();
      refreshList();
    });
  };

  return (
    <header
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 10,
        padding: '12px 16px',
        borderBottom: '1px solid #e5e7eb',
        background: '#fff',
      }}
    >
      <strong style={{ fontSize: 18, marginRight: 8 }}>AI Workflow Builder</strong>

      <input
        aria-label="Pipeline name"
        value={pipelineName}
        onChange={(e) => setPipelineName(e.target.value)}
        style={{ ...inputStyle, minWidth: 200 }}
      />
      <button type="button" onClick={save} disabled={busy} style={buttonStyle('primary')}>
        {pipelineId ? 'Save' : 'Save as new'}
        {dirty ? ' •' : ''}
      </button>

      <select
        aria-label="Open pipeline"
        value=""
        onChange={(e) => open(e.target.value)}
        style={inputStyle}
      >
        <option value="">Open…</option>
        {pipelines.map((pipeline) => (
          <option key={pipeline.id} value={pipeline.id}>
            {pipeline.name}
          </option>
        ))}
      </select>

      <button
        type="button"
        onClick={() => confirmDiscard() && newPipeline()}
        style={buttonStyle('secondary')}
      >
        New
      </button>
      {pipelineId && (
        <button type="button" onClick={remove} disabled={busy} style={buttonStyle('danger')}>
          Delete
        </button>
      )}

      {message && <span style={{ fontSize: 14, color: '#6b7280' }}>{message}</span>}

      <span style={{ marginLeft: 'auto', fontSize: 14, color: '#6b7280' }}>{user?.email}</span>
      <button type="button" onClick={logout} style={buttonStyle('secondary')}>
        Log out
      </button>
    </header>
  );
};
