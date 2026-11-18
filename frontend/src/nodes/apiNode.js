import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';

export const APINode = ({ id }) => {
  return (
    <BaseNode
      id={id}
      title="API"
      handles={[
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-input`,
        },
        {
          type: 'source',
          position: Position.Right,
          id: `${id}-output`,
        },
      ]}
    >
      <div>API Request Node</div>
      <span style={{ fontSize: 12, color: '#6b7280' }}>Not executable yet</span>
    </BaseNode>
  );
};