// Side drawer listing past runs (newest first) with their inputs, outputs, errors and per-node
// results. Runs of the open pipeline can be shown on the canvas or re-run with the same inputs.

import { useEffect, useRef } from 'react';
import { shallow } from 'zustand/shallow';
import { useStore } from './store';
import { formatDateTime, formatDuration, formatRelative, formatTokens } from './format';

const selector = (state) => ({
  historyOpen: state.historyOpen,
  historyScope: state.historyScope,
  history: state.history,
  selectedRunId: state.selectedRunId,
  pipelineId: state.pipelineId,
  pipelineName: state.pipelineName,
  dirty: state.dirty,
  polling: state.polling,
  closeHistory: state.closeHistory,
  setHistoryScope: state.setHistoryScope,
  loadHistory: state.loadHistory,
  selectRun: state.selectRun,
  runMatchesCanvas: state.runMatchesCanvas,
  showRunOnCanvas: state.showRunOnCanvas,
  rerunWithInputs: state.rerunWithInputs,
  openPipeline: state.openPipeline,
});

const KeyValues = ({ title, values }) => {
  const entries = Object.entries(values || {});
  if (entries.length === 0) return null;
  return (
    <div className="history__section">
      <div className="history__label">{title}</div>
      {entries.map(([name, value]) => (
        <div key={name} className="history__kv">
          <span className="history__key">{name}</span>
          <pre className="history__value">{String(value)}</pre>
        </div>
      ))}
    </div>
  );
};

const RunDetails = ({ run, store }) => {
  const matches = store.runMatchesCanvas(run);
  const nodeEntries = Object.entries(run.node_states || {});
  const busyReason = store.polling ? 'Wait for the current run to finish' : null;

  const openPipeline = () => {
    if (store.dirty && !window.confirm('Discard unsaved changes?')) return;
    store.openPipeline(run.pipeline_id).catch((err) => window.alert(err.message));
  };

  return (
    <div className="history__details">
      <div className="history__meta text-muted">
        Started {formatDateTime(run.created_at)}
        {formatDuration(run.started_at, run.finished_at) && ` · took ${formatDuration(run.started_at, run.finished_at)}`}
        {formatTokens(run) && ` · ${formatTokens(run)}`}
      </div>

      {run.error && <div className="text-danger history__section">{run.error}</div>}
      <KeyValues title="Inputs" values={run.inputs} />
      <KeyValues title="Outputs" values={run.outputs} />

      {nodeEntries.length > 0 && (
        <div className="history__section">
          <div className="history__label">Nodes</div>
          <ul className="history__nodes">
            {nodeEntries.map(([nodeId, state]) => (
              <li key={nodeId}>
                <span className={`status-dot status-dot--${state.status}`} aria-hidden="true" />
                <span className="history__node-id">{nodeId}</span>
                <span className={`status-${state.status}`}>{state.status}</span>
                {state.error && <div className="history__node-error">{state.error}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="row">
        {matches ? (
          <>
            <button
              type="button"
              className="btn btn--small"
              onClick={() => store.showRunOnCanvas(run)}
              disabled={store.polling}
              title={busyReason || 'Colour the canvas with this run’s node results'}
            >
              Show on canvas
            </button>
            <button
              type="button"
              className="btn btn--small btn--primary"
              onClick={() => store.rerunWithInputs(run)}
              disabled={store.polling}
              title={busyReason || 'Run the current pipeline again with these inputs'}
            >
              Run again with these inputs
            </button>
          </>
        ) : run.pipeline_id && run.pipeline_name ? (
          <button type="button" className="btn btn--small" onClick={openPipeline}>
            Open “{run.pipeline_name}”
          </button>
        ) : (
          <span className="hint">
            {run.pipeline_id ? 'This pipeline was deleted.' : 'Run of an unsaved pipeline.'}
          </span>
        )}
      </div>
    </div>
  );
};

export const RunHistory = () => {
  const store = useStore(selector, shallow);
  const { historyOpen, historyScope, history, selectedRunId, pipelineId, pipelineName, closeHistory } = store;
  const closeButton = useRef(null);

  // Focus the drawer when it opens; Escape closes it.
  useEffect(() => {
    if (!historyOpen) return undefined;
    closeButton.current?.focus();
    const onKey = (event) => event.key === 'Escape' && closeHistory();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [historyOpen, closeHistory]);

  if (!historyOpen) return null;

  const showingPipeline = historyScope === 'pipeline';
  let emptyMessage = 'No runs yet.';
  if (showingPipeline && !pipelineId) emptyMessage = 'Save this pipeline to keep a history of its runs, or view all runs.';
  else if (showingPipeline) emptyMessage = `“${pipelineName}” hasn’t been run yet.`;

  return (
    <aside id="run-history" className="history" aria-label="Run history">
      <div className="history__header">
        <h2 className="history__title">Run history</h2>
        <button ref={closeButton} type="button" className="btn btn--small" onClick={store.closeHistory} aria-label="Close run history">
          ✕
        </button>
      </div>

      <div className="segmented" role="group" aria-label="Which runs">
        <button
          type="button"
          className={`segmented__option${showingPipeline ? ' segmented__option--active' : ''}`}
          aria-pressed={showingPipeline}
          onClick={() => store.setHistoryScope('pipeline')}
        >
          This pipeline
        </button>
        <button
          type="button"
          className={`segmented__option${!showingPipeline ? ' segmented__option--active' : ''}`}
          aria-pressed={!showingPipeline}
          onClick={() => store.setHistoryScope('all')}
        >
          All runs
        </button>
        <button type="button" className="btn btn--small history__refresh" onClick={() => store.loadHistory()} disabled={history.loading}>
          Refresh
        </button>
      </div>

      {history.error && (
        <div role="alert" className="text-danger">
          Couldn’t load runs: {history.error}
        </div>
      )}

      {history.items.length === 0 && !history.loading && !history.error && (
        <p className="text-muted">{emptyMessage}</p>
      )}

      <ul className="history__list">
        {history.items.map((run) => {
          const selected = run.id === selectedRunId;
          const duration = formatDuration(run.started_at, run.finished_at);
          return (
            <li key={run.id} className={`history__item${selected ? ' history__item--selected' : ''}`}>
              <button
                type="button"
                className="history__summary"
                onClick={() => store.selectRun(run.id)}
                aria-expanded={selected}
              >
                <span className={`status-dot status-dot--${run.status}`} aria-hidden="true" />
                <span className="history__summary-main">
                  <span className={`history__status status-${run.status}`}>{run.status}</span>
                  {!showingPipeline && (
                    <span className="history__pipeline">{run.pipeline_name || 'Unsaved pipeline'}</span>
                  )}
                </span>
                <span className="history__summary-side text-muted">
                  <time dateTime={run.created_at} title={formatDateTime(run.created_at)}>
                    {formatRelative(run.created_at)}
                  </time>
                  {duration && <span>{duration}</span>}
                </span>
              </button>
              {selected && <RunDetails run={run} store={store} />}
            </li>
          );
        })}
      </ul>

      {history.loading && <p className="text-muted">Loading…</p>}
      {history.nextCursor && !history.loading && (
        <button type="button" className="btn history__more" onClick={() => store.loadHistory({ more: true })}>
          Load older runs
        </button>
      )}
    </aside>
  );
};
