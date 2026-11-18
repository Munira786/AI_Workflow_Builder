// outputNode.js

import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';
import { useStore } from '../store';

export const defaultOutputName = (id) => id.replace('customOutput-', 'output_');

export const OutputNode = ({ id, data }) => {
  const updateNodeField = useStore((state) => state.updateNodeField);
  const name = data?.outputName ?? defaultOutputName(id);
  const outputType = data?.outputType || 'Text';

  return (
    <BaseNode
      id={id}
      title="Output"
      handles={[
        {
          type: 'target',
          position: Position.Left,
          id: `${id}-value`,
          label: 'value',
        },
      ]}
    >
      <label>
        Name:{' '}
        <input
          type="text"
          className="nodrag"
          value={name}
          onChange={(e) => updateNodeField(id, 'outputName', e.target.value)}
        />
      </label>
      <label>
        Type:{' '}
        <select
          className="nodrag"
          value={outputType}
          onChange={(e) => updateNodeField(id, 'outputType', e.target.value)}
        >
          <option value="Text">Text</option>
          <option value="File">Image</option>
        </select>
      </label>
    </BaseNode>
  );
};
