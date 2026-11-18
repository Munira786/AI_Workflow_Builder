// The React Flow canvas: drop nodes from the toolbar, connect, move, delete.

import { useCallback, useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import { shallow } from 'zustand/shallow';
import { useStore } from './store';
import { buildNodeTypes, componentFor } from './nodes/registry';
import { DRAG_MIME } from './Toolbar';

const GRID_SIZE = 20;
const proOptions = { hideAttribution: true };

const selector = (state) => ({
  catalog: state.catalog,
  nodes: state.nodes,
  edges: state.edges,
  addNodeOfType: state.addNodeOfType,
  onNodesChange: state.onNodesChange,
  onEdgesChange: state.onEdgesChange,
  onConnect: state.onConnect,
});

export const Canvas = () => {
  const [flow, setFlow] = useState(null);
  const { catalog, nodes, edges, addNodeOfType, onNodesChange, onEdgesChange, onConnect } =
    useStore(selector, shallow);

  // Saved pipelines may contain types the catalogue no longer lists; render those too.
  // Keyed on the set of types so it's recomputed when a type appears, not on every node move.
  const typesKey = [...new Set(nodes.map((node) => node.type))].join('|');
  const nodeTypes = useMemo(() => {
    const types = buildNodeTypes(catalog);
    for (const type of typesKey.split('|')) if (type && !types[type]) types[type] = componentFor(type);
    return types;
  }, [catalog, typesKey]);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const raw = event.dataTransfer?.getData(DRAG_MIME);
      if (!raw || !flow) return;
      let type;
      try {
        type = JSON.parse(raw)?.nodeType;
      } catch {
        return;
      }
      if (!type) return;
      addNodeOfType(type, flow.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
    },
    [flow, addNodeOfType],
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  return (
    <div className="canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onInit={setFlow}
        nodeTypes={nodeTypes}
        proOptions={proOptions}
        snapGrid={[GRID_SIZE, GRID_SIZE]}
        connectionLineType="smoothstep"
      >
        <Background color="#d1d5db" gap={GRID_SIZE} />
        <Controls />
        <MiniMap zoomable pannable />
      </ReactFlow>
    </div>
  );
};
