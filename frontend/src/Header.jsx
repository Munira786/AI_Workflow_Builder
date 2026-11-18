// Pipeline name, save / open / new / delete, and the signed-in user.

import { useCallback, useEffect, useState } from 'react';
import { shallow } from 'zustand/shallow';
import { useStore } from './store';
import { api, serializeGraph } from './api';
import { useAuth } from './AuthContext';

const PIPELINE_LIST_LIMIT = 100;

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
    api(`/pipelines?limit=${PIPELINE_LIST_LIMIT}`)
      .then((page) => setPipelines(page.items))
      .catch((err) => setMessage(err.message));
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  // Warn before closing or reloading the tab with unsaved changes.
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  // "Saved" fades after a few seconds instead of sticking forever.
  useEffect(() => {
    if (message !== 'Saved') return undefined;
    const timer = setTimeout(() => setMessage(''), 3000);
    return () => clearTimeout(timer);
  }, [message]);

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
    <header className="header">
      <strong className="header__brand">AI Workflow Builder</strong>

      <input
        aria-label="Pipeline name"
        value={pipelineName}
        onChange={(e) => setPipelineName(e.target.value)}
        className="input header__name"
      />
      <button type="button" onClick={save} disabled={busy} className="btn btn--primary">
        {pipelineId ? 'Save' : 'Save as new'}
        {dirty ? ' •' : ''}
      </button>

      <select aria-label="Open pipeline" value="" onChange={(e) => open(e.target.value)} className="input">
        <option value="">Open…</option>
        {pipelines.map((pipeline) => (
          <option key={pipeline.id} value={pipeline.id}>
            {pipeline.name}
          </option>
        ))}
      </select>

      <button type="button" onClick={() => confirmDiscard() && newPipeline()} className="btn">
        New
      </button>
      {pipelineId && (
        <button type="button" onClick={remove} disabled={busy} className="btn btn--danger">
          Delete
        </button>
      )}

      {message && <span className="text-muted">{message}</span>}

      <span className="header__user text-muted">{user?.email}</span>
      <button type="button" onClick={() => confirmDiscard() && logout()} className="btn">
        Log out
      </button>
    </header>
  );
};
