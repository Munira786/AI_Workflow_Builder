// store.js

import { create } from 'zustand';
import {
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from 'reactflow';

const UNTITLED = 'Untitled pipeline';

export const useStore = create((set, get) => ({
  nodes: [],
  edges: [],
  nodeIDs: {},

  // Saved-pipeline metadata
  pipelineId: null,
  pipelineName: UNTITLED,
  dirty: false,

  // Live run status per node id: { status, output?, error? }
  nodeStatuses: {},

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
  addNode: (node) => {
    set({ nodes: [...get().nodes, node], dirty: true });
  },
  onNodesChange: (changes) => {
    const structural = changes.some((change) => change.type !== 'select' && change.type !== 'dimensions');
    set({ nodes: applyNodeChanges(changes, get().nodes), dirty: get().dirty || structural });
  },
  onEdgesChange: (changes) => {
    const structural = changes.some((change) => change.type !== 'select');
    set({ edges: applyEdgeChanges(changes, get().edges), dirty: get().dirty || structural });
  },
  onConnect: (connection) => {
    set({
      edges: addEdge({
        ...connection, type: 'smoothstep', animated: true,
        style: {
          stroke: '#22c55e',
          strokeWidth: 3,
        }, markerEnd: { type: MarkerType.Arrow, height: '20px', width: '20px' }
      }, get().edges),
      dirty: true,
    });
  },
  updateNodeField: (nodeId, fieldName, fieldValue) => {
    set({
      nodes: get().nodes.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, [fieldName]: fieldValue } } : node
      ),
      dirty: true,
    });
  },

  setPipelineName: (pipelineName) => set({ pipelineName, dirty: true }),
  markSaved: (pipeline) => set({ pipelineId: pipeline.id, pipelineName: pipeline.name, dirty: false }),
  loadPipeline: (pipeline) =>
    set({
      pipelineId: pipeline.id,
      pipelineName: pipeline.name,
      nodes: pipeline.graph.nodes,
      edges: pipeline.graph.edges,
      nodeIDs: {},
      nodeStatuses: {},
      dirty: false,
    }),
  newPipeline: () =>
    set({
      pipelineId: null,
      pipelineName: UNTITLED,
      nodes: [],
      edges: [],
      nodeIDs: {},
      nodeStatuses: {},
      dirty: false,
    }),
  setNodeStatuses: (nodeStatuses) => set({ nodeStatuses }),
}));
