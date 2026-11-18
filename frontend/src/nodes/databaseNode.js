import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';

export const DatabaseNode = ({ id }) => {
  return (
    <BaseNode
      id={id}
      title="Database"
      handles={[
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-query`,
        },
        {
          type: 'source',
          position: Position.Right,
          id: `${id}-result`,
        },
      ]}
    >
      <div>Database Query</div>
      <span style={{ fontSize: 12, color: '#6b7280' }}>Not executable yet</span>
    </BaseNode>
  );
};