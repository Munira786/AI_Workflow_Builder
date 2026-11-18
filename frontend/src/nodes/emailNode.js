import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';

export const EmailNode = ({ id }) => {
  return (
    <BaseNode
      id={id}
      title="Email"
      handles={[
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-message`,
        },
        {
          type: 'source',
          position: Position.Right,
          id: `${id}-sent`,
        },
      ]}
    >
      <div>Send Email</div>
      <span style={{ fontSize: 12, color: '#6b7280' }}>Not executable yet</span>
    </BaseNode>
  );
};