// RunPanel.js
// Values for the pipeline's Input nodes, Analyze / Run buttons, and live run status + outputs.

import { useEffect, useRef, useState } from 'react';
import { useStore } from './store';
import { shallow } from 'zustand/shallow';
import { api, serializeGraph } from './api';
import { defaultInputName } from './nodes/inputNode';
import { STATUS_COLORS, buttonStyle, inputStyle } from './styles';

const POLL_INTERVAL_MS = 1000;
const TERMINAL = new Set(['succeeded', 'failed']);

const selector = (state) => ({
  nodes: state.nodes,
  edges: state.edges,
  pipelineId: state.pipelineId,
  setNodeStatuses: state.setNodeStatuses,
});

export const RunPanel = () => {
  const { nodes, edges, pipelineId, setNodeStatuses } = useStore(selector, shallow);
  const [inputValues, setInputValues] = useState({});
  const [run, setRun] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const pollTimer = useRef(null);

  const inputNames = nodes
    .filter((node) => node.type === 'customInput')
    .map((node) => node.data?.inputName ?? defaultInputName(node.id));

  const stopPolling = () => clearTimeout(pollTimer.current);
  useEffect(() => stopPolling, []);

  const poll = async (runId) => {
    try {
      const latest = await api(`/runs/${runId}`);
      setRun(latest);
      setNodeStatuses(latest.node_states);
      if (!TERMINAL.has(latest.status)) {
        pollTimer.current = setTimeout(() => poll(runId), POLL_INTERVAL_MS);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const startRun = async () => {
    stopPolling();
    setError('');
    setAnalysis(null);
    setNodeStatuses({});
    try {
      const inputs = Object.fromEntries(inputNames.map((name) => [name, inputValues[name] ?? '']));
      const created = await api('/runs', {
        method: 'POST',
        body: { graph: serializeGraph(nodes, edges), pipeline_id: pipelineId, inputs },
      });
      setRun(created);
      poll(created.id);
    } catch (err) {
      setRun(null);
      setError(err.message);
    }
  };

  const analyze = async () => {
    setError('');
    try {
      setAnalysis(await api('/pipelines/parse', { method: 'POST', body: serializeGraph(nodes, edges) }));
    } catch (err) {
      setError(err.message);
    }
  };

  const running = run && !TERMINAL.has(run.status);

  return (
    <section
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: 16,
        borderTop: '1px solid #e5e7eb',
        background: '#f8fafc',
      }}
    >
      {inputNames.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {inputNames.map((name) => (
            <label key={name} style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 14 }}>
              {name}
              <input
                value={inputValues[name] ?? ''}
                onChange={(e) => setInputValues({ ...inputValues, [name]: e.target.value })}
                style={{ ...inputStyle, minWidth: 220 }}
              />
            </label>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
        <button type="button" onClick={startRun} disabled={running || nodes.length === 0} style={buttonStyle('primary')}>
          {running ? 'Running…' : 'Run pipeline'}
        </button>
        <button type="button" onClick={analyze} disabled={nodes.length === 0} style={buttonStyle('secondary')}>
          Analyze
        </button>

        {run && (
          <span style={{ fontWeight: 600, color: STATUS_COLORS[run.status] }}>Status: {run.status}</span>
        )}
        {analysis && (
          <span style={{ fontSize: 14 }}>
            {analysis.num_nodes} nodes · {analysis.num_edges} edges ·{' '}
            {analysis.is_dag ? 'valid DAG' : 'contains a cycle'}
          </span>
        )}
      </div>

      {error && <div role="alert" style={{ color: STATUS_COLORS.failed }}>{error}</div>}
      {run?.error && <div role="alert" style={{ color: STATUS_COLORS.failed }}>{run.error}</div>}

      {run?.status === 'succeeded' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Object.keys(run.outputs).length === 0 && (
            <span style={{ color: '#6b7280' }}>Run finished. Add an Output node to see results here.</span>
          )}
          {Object.entries(run.outputs).map(([name, value]) => (
            <div key={name}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{name}</div>
              <pre
                style={{
                  margin: 0,
                  padding: 12,
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 8,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'inherit',
                }}
              >
                {value}
              </pre>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
