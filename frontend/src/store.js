import { create } from 'zustand';
import { addEdge, applyNodeChanges, applyEdgeChanges, MarkerType } from 'reactflow';
import { api, serializeGraph } from './api';
import { effectiveName, indexByType, initialData } from './catalog';

const UNTITLED = 'Untitled pipeline';

export const POLL_INTERVAL_MS = 1000;
export const MAX_POLL_FAILURES = 5;
const TERMINAL = new Set(['succeeded', 'failed']);

// Polling lives outside React so it survives re-renders and can be cancelled from anywhere
// (opening another pipeline, logging out). Each run gets a generation number; a response that
// arrives for an older generation is ignored, so a stale run can never paint the new canvas.
let pollTimer = null;
let pollGeneration = 0;

const cancelPolling = () => {
  pollGeneration += 1;
  clearTimeout(pollTimer);
  pollTimer = null;
};

const emptyRunState = { run: null, runError: '', polling: false, nodeStatuses: {} };

export const HISTORY_PAGE_SIZE = 20;
const emptyHistory = { items: [], nextCursor: null, loading: false, error: '' };
// Same idea as pollGeneration: only the latest history request may update the list.
let historyRequest = 0;

export const useStore = create((set, get) => {
  /** Structural edits invalidate the statuses shown from the last finished run. */
  const edited = (patch) => {
    const stale = !get().polling && Object.keys(get().nodeStatuses).length > 0;
    set({ ...patch, dirty: true, ...(stale ? { nodeStatuses: {} } : {}) });
  };

  const poll = async (runId, generation, failures) => {
    if (generation !== pollGeneration) return;
    let latest;
    try {
      latest = await api(`/runs/${runId}`);
    } catch (err) {
      if (generation !== pollGeneration) return;
      const fatal = err.status === 401 || err.status === 404 || failures + 1 >= MAX_POLL_FAILURES;
      if (fatal) {
        set({ polling: false, runError: `Stopped following the run: ${err.message}` });
        return;
      }
      set({ runError: `Connection problem, retrying… (${err.message})` });
      pollTimer = setTimeout(
        () => poll(runId, generation, failures + 1),
        POLL_INTERVAL_MS * 2 ** (failures + 1),
      );
      return;
    }
    if (generation !== pollGeneration) return;
    const finished = TERMINAL.has(latest.status);
    set({ run: latest, nodeStatuses: latest.node_states, polling: !finished, runError: '' });
    if (finished && get().historyOpen) get().loadHistory();
    if (!finished) pollTimer = setTimeout(() => poll(runId, generation, 0), POLL_INTERVAL_MS);
  };

  return {
    // ---- Node catalogue (GET /node-types) ----
    catalog: null,
    specs: {},
    catalogError: '',
    loadCatalog: async () => {
      set({ catalogError: '' });
      try {
        const catalog = await api('/node-types');
        set({ catalog, specs: indexByType(catalog) });
      } catch (err) {
        set({ catalogError: err.message });
      }
    },

    // ---- Canvas ----
    nodes: [],
    edges: [],
    nodeIDs: {},

    getNodeID: (type) => {
      // Never reuse an id already on the canvas (matters after loading a saved pipeline).
      const prefix = `${type}-`;
      const used = get()
        .nodes.filter((node) => node.id.startsWith(prefix))
        .map((node) => parseInt(node.id.slice(prefix.length), 10))
        .filter(Number.isFinite);
      const next = Math.max(0, get().nodeIDs[type] || 0, ...used) + 1;
      set({ nodeIDs: { ...get().nodeIDs, [type]: next } });
      return `${type}-${next}`;
    },
    addNodeOfType: (type, position) => {
      const spec = get().specs[type];
      if (!spec) return;
      const id = get().getNodeID(type);
      edited({ nodes: [...get().nodes, { id, type, position, data: initialData(spec, id) }] });
    },
    onNodesChange: (changes) => {
      const structural = changes.some((change) => change.type !== 'select' && change.type !== 'dimensions');
      const nodes = applyNodeChanges(changes, get().nodes);
      if (structural) edited({ nodes });
      else set({ nodes });
    },
    onEdgesChange: (changes) => {
      const structural = changes.some((change) => change.type !== 'select');
      const edges = applyEdgeChanges(changes, get().edges);
      if (structural) edited({ edges });
      else set({ edges });
    },
    onConnect: (connection) => {
      edited({
        edges: addEdge(
          {
            ...connection,
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#22c55e', strokeWidth: 3 },
            markerEnd: { type: MarkerType.Arrow, height: '20px', width: '20px' },
          },
          get().edges,
        ),
      });
    },
    updateNodeField: (nodeId, fieldName, fieldValue) => {
      edited({
        nodes: get().nodes.map((node) =>
          node.id === nodeId ? { ...node, data: { ...node.data, [fieldName]: fieldValue } } : node,
        ),
      });
    },

    // ---- Saved-pipeline metadata ----
    pipelineId: null,
    pipelineName: UNTITLED,
    dirty: false,

    setPipelineName: (pipelineName) => set({ pipelineName, dirty: true }),
    markSaved: (pipeline) => set({ pipelineId: pipeline.id, pipelineName: pipeline.name, dirty: false }),
    loadPipeline: (pipeline) => {
      cancelPolling();
      set({
        ...emptyRunState,
        runInputs: {},
        pipelineId: pipeline.id,
        pipelineName: pipeline.name,
        nodes: pipeline.graph.nodes,
        edges: pipeline.graph.edges,
        nodeIDs: {},
        dirty: false,
        selectedRunId: null,
      });
      if (get().historyOpen) get().loadHistory();
    },
    openPipeline: async (pipelineId) => {
      get().loadPipeline(await api(`/pipelines/${pipelineId}`));
    },
    newPipeline: () => {
      cancelPolling();
      set({
        ...emptyRunState,
        runInputs: {},
        pipelineId: null,
        pipelineName: UNTITLED,
        nodes: [],
        edges: [],
        nodeIDs: {},
        dirty: false,
        selectedRunId: null,
      });
      if (get().historyOpen) get().loadHistory();
    },

    // ---- Runs ----
    ...emptyRunState,
    runInputs: {},
    setRunInput: (name, value) => set({ runInputs: { ...get().runInputs, [name]: value } }),

    /** Effective names of the canvas's Input nodes (what the backend will look up). */
    inputNames: () => {
      const spec = get().specs.customInput;
      if (!spec) return [];
      const names = get().nodes.filter((n) => n.type === spec.type).map((n) => effectiveName(spec, n));
      return [...new Set(names)];
    },

    startRun: async () => {
      const inputs = Object.fromEntries(get().inputNames().map((name) => [name, get().runInputs[name] ?? '']));
      cancelPolling();
      const generation = pollGeneration;
      set({ ...emptyRunState, polling: true });
      const { nodes, edges, pipelineId } = get();
      let created;
      try {
        created = await api('/runs', {
          method: 'POST',
          body: { graph: serializeGraph(nodes, edges), pipeline_id: pipelineId, inputs },
        });
      } catch (err) {
        if (generation === pollGeneration) set({ polling: false, runError: err.message });
        return;
      }
      if (generation !== pollGeneration) return;
      set({ run: created });
      if (get().historyOpen) get().loadHistory();
      poll(created.id, generation, 0);
    },
    stopFollowingRun: () => {
      cancelPolling();
      set({ polling: false });
    },
    resetSession: () => {
      cancelPolling();
      historyRequest += 1;
      set({ ...emptyRunState, historyOpen: false, history: emptyHistory, historyScope: 'pipeline' });
      get().newPipeline();
    },

    // ---- Run history ----
    historyOpen: false,
    historyScope: 'pipeline', // 'pipeline' (the open saved pipeline) or 'all'
    history: emptyHistory,
    selectedRunId: null,

    toggleHistory: () => {
      const open = !get().historyOpen;
      set({ historyOpen: open });
      if (open) get().loadHistory();
    },
    closeHistory: () => set({ historyOpen: false }),
    setHistoryScope: (historyScope) => {
      set({ historyScope, selectedRunId: null });
      get().loadHistory();
    },
    /** First page (default) or, with more=true, the next page after the loaded items. */
    loadHistory: async ({ more = false } = {}) => {
      const { history, historyScope, pipelineId } = get();
      if (more && !history.nextCursor) return;
      const request = ++historyRequest;
      const params = new URLSearchParams({ limit: String(HISTORY_PAGE_SIZE) });
      if (historyScope === 'pipeline' && pipelineId) params.set('pipeline_id', pipelineId);
      if (more) params.set('cursor', history.nextCursor);
      // An unsaved pipeline has no runs of its own yet; show nothing rather than everything.
      if (historyScope === 'pipeline' && !pipelineId) {
        set({ history: emptyHistory });
        return;
      }
      set({ history: { ...get().history, loading: true, error: '' } });
      let page;
      try {
        page = await api(`/runs?${params}`);
      } catch (err) {
        if (request === historyRequest) set({ history: { ...get().history, loading: false, error: err.message } });
        return;
      }
      if (request !== historyRequest) return;
      set({
        history: {
          items: more ? [...get().history.items, ...page.items] : page.items,
          nextCursor: page.next_cursor,
          loading: false,
          error: '',
        },
      });
    },
    selectRun: (runId) => set({ selectedRunId: get().selectedRunId === runId ? null : runId }),
    /** A run can be shown on / re-run from the canvas only if it belongs to the open pipeline. */
    runMatchesCanvas: (run) => Boolean(run.pipeline_id) && run.pipeline_id === get().pipelineId,
    showRunOnCanvas: (run) => {
      if (get().polling || !get().runMatchesCanvas(run)) return;
      set({ run, nodeStatuses: run.node_states, runError: '' });
    },
    rerunWithInputs: (run) => {
      if (get().polling || !get().runMatchesCanvas(run)) return;
      set({ runInputs: { ...get().runInputs, ...run.inputs } });
      get().startRun();
    },
  };
});
