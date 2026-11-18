// llmNode.js

import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';

const labelStyle = { fontSize: 12, color: '#6b7280' };

export const LLMNode = ({ id }) => {
  return (
    <BaseNode
      id={id}
      title="LLM"
      handles={[
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-system`,
          label: 'system',
          style: { top: `${100 / 3}%` },
        },
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-prompt`,
          label: 'prompt',
          style: { top: `${200 / 3}%` },
        },
        {
          type: 'source',
          position: Position.Right,
          id: `${id}-response`,
          label: 'response',
        },
      ]}
    >
      <span>Calls Claude with a prompt.</span>
      <span style={labelStyle}>Inputs: system (optional), prompt → response</span>
    </BaseNode>
  );
};
