import { create } from 'zustand';
import { addEdge, applyNodeChanges, applyEdgeChanges, MarkerType } from 'reactflow';
import { api, serializeGraph } from './api';
import { indexByType, initialData } from './catalog';

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
      });
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
      });
    },

    // ---- Runs ----
    ...emptyRunState,
    runInputs: {},
    setRunInput: (name, value) => set({ runInputs: { ...get().runInputs, [name]: value } }),

    startRun: async (inputs) => {
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
      poll(created.id, generation, 0);
    },
    stopFollowingRun: () => {
      cancelPolling();
      set({ polling: false });
    },
    resetSession: () => {
      cancelPolling();
      set({ ...emptyRunState, catalog: get().catalog, specs: get().specs });
      get().newPipeline();
    },
  };
});
