// textNode.js

import { useEffect, useMemo } from 'react';
import { Position, useUpdateNodeInternals } from 'reactflow';
import { BaseNode } from './BaseNode';
import { useStore } from '../store';

const VARIABLE_REGEX = /{{\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*}}/g;

export const TextNode = ({ id, data }) => {
  const updateNodeField = useStore((state) => state.updateNodeField);
  const updateNodeInternals = useUpdateNodeInternals();
  const text = data?.text ?? '{{input}}';

  // Extract unique variables like {{name}}; each becomes an input handle.
  const variables = useMemo(
    () => [...new Set([...text.matchAll(VARIABLE_REGEX)].map((match) => match[1]))],
    [text]
  );
  const variablesKey = variables.join(',');

  // Refresh React Flow's handle positions when the set of variables changes.
  useEffect(() => {
    updateNodeInternals(id);
  }, [variablesKey, id, updateNodeInternals]);

  const variableHandles = variables.map((variable, index) => ({
    type: 'target',
    position: Position.Left,
    id: `${id}-${variable}`,
    label: variable,
    style: { top: `${80 + index * 30}px` },
  }));

  // Grow the node with its content.
  const lines = text.split('\n');
  const longestLine = Math.max(...lines.map((line) => line.length));
  const nodeWidth = Math.min(500, Math.max(250, longestLine * 8));
  const nodeHeight = Math.max(120, 80 + lines.length * 25, 80 + variables.length * 30);

  return (
    <BaseNode
      id={id}
      title="Text"
      width={nodeWidth}
      minHeight={nodeHeight}
      handles={[
        ...variableHandles,
        {
          type: 'source',
          position: Position.Right,
          id: `${id}-output`,
          label: 'output',
        },
      ]}
    >
      <textarea
        className="nodrag"
        value={text}
        onChange={(e) => updateNodeField(id, 'text', e.target.value)}
        style={{
          width: '100%',
          minHeight: '80px',
          resize: 'none',
          boxSizing: 'border-box',
          fontFamily: 'inherit',
        }}
      />
      {variables.length > 0 && (
        <span style={{ fontSize: 12, color: '#6b7280' }}>Inputs: {variables.join(', ')}</span>
      )}
    </BaseNode>
  );
};
