// Values for the pipeline's Input nodes, Analyze / Run buttons, and live run status + outputs.
// Run state and polling live in the store (store.js); this component only displays them.

import { useState } from 'react';
import { shallow } from 'zustand/shallow';
import { useStore } from './store';
import { api, serializeGraph } from './api';
import { formatTokens } from './format';

const selector = (state) => ({
  nodes: state.nodes,
  edges: state.edges,
  inputNames: state.inputNames,
  run: state.run,
  runError: state.runError,
  polling: state.polling,
  runInputs: state.runInputs,
  setRunInput: state.setRunInput,
  startRun: state.startRun,
  historyOpen: state.historyOpen,
  toggleHistory: state.toggleHistory,
});

export const RunPanel = () => {
  const {
    nodes, edges, inputNames: getInputNames, run, runError, polling, runInputs, setRunInput, startRun,
    historyOpen, toggleHistory,
  } = useStore(selector, shallow);
  const [analysis, setAnalysis] = useState(null);
  const [analyzeError, setAnalyzeError] = useState('');

  const inputNames = getInputNames(); // re-evaluated on every render; nodes are subscribed above

  const onRun = () => {
    setAnalysis(null);
    startRun();
  };

  const analyze = async () => {
    setAnalyzeError('');
    try {
      setAnalysis(await api('/pipelines/parse', { method: 'POST', body: serializeGraph(nodes, edges) }));
    } catch (err) {
      setAnalyzeError(err.message);
    }
  };

  const tokens = run ? formatTokens(run) : null;

  return (
    <section className="run-panel" aria-label="Run">
      {inputNames.length > 0 && (
        <div className="row">
          {inputNames.map((name) => (
            <label key={name} className="field">
              {name}
              <input
                value={runInputs[name] ?? ''}
                onChange={(e) => setRunInput(name, e.target.value)}
                className="input run-panel__input"
              />
            </label>
          ))}
        </div>
      )}

      <div className="row">
        <button type="button" onClick={onRun} disabled={polling || nodes.length === 0} className="btn btn--primary">
          {polling ? 'Running…' : 'Run pipeline'}
        </button>
        <button type="button" onClick={analyze} disabled={nodes.length === 0} className="btn">
          Analyze
        </button>
        <button
          type="button"
          onClick={toggleHistory}
          className={`btn${historyOpen ? ' btn--active' : ''}`}
          aria-expanded={historyOpen}
          aria-controls="run-history"
        >
          History
        </button>

        {run && <span className={`run-panel__status status-${run.status}`}>Status: {run.status}</span>}
        {tokens && <span className="text-muted">{tokens}</span>}
        {analysis && (
          <span>
            {analysis.num_nodes} nodes · {analysis.num_edges} edges ·{' '}
            {analysis.is_dag ? 'valid DAG' : 'contains a cycle'}
          </span>
        )}
      </div>

      {(runError || analyzeError) && <div role="alert" className="text-danger">{runError || analyzeError}</div>}
      {run?.error && <div role="alert" className="text-danger">{run.error}</div>}

      {run?.status === 'succeeded' && (
        <div className="stack">
          {Object.keys(run.outputs).length === 0 && (
            <span className="text-muted">Run finished. Add an Output node to see results here.</span>
          )}
          {Object.entries(run.outputs).map(([name, value]) => (
            <div key={name}>
              <div className="run-panel__output-name">{name}</div>
              <pre className="run-panel__output">{value}</pre>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
