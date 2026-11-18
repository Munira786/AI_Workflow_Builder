import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';

export const FilterNode = ({ id }) => {
  return (
    <BaseNode
      id={id}
      title="Filter"
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
      <div>Filter Data</div>
      <span style={{ fontSize: 12, color: '#6b7280' }}>Not executable yet</span>
    </BaseNode>
  );
};