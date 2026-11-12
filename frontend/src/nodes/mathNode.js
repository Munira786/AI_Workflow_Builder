import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';

export const MathNode = ({ id }) => {
  return (
    <BaseNode
      id={id}
      title="Math"
      handles={[
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-input`,
        },
        {
          type: 'source',
          position: Position.Right,
          id: `${id}-result`,
        },
      ]}
    >
      <div>Math Operation</div>
      <span style={{ fontSize: 12, color: '#6b7280' }}>Not executable yet</span>
    </BaseNode>
  );
};