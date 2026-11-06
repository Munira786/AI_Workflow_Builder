// inputNode.js

import { Position } from 'reactflow';
import { BaseNode } from './BaseNode';
import { useStore } from '../store';

export const defaultInputName = (id) => id.replace('customInput-', 'input_');

export const InputNode = ({ id, data }) => {
  const updateNodeField = useStore((state) => state.updateNodeField);
  const name = data?.inputName ?? defaultInputName(id);
  const inputType = data?.inputType || 'Text';

  return (
    <BaseNode
      id={id}
      title="Input"
      handles={[
        {
          type: 'source',
          position: Position.Right,
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
          onChange={(e) => updateNodeField(id, 'inputName', e.target.value)}
        />
      </label>
      <label>
        Type:{' '}
        <select
          className="nodrag"
          value={inputType}
          onChange={(e) => updateNodeField(id, 'inputType', e.target.value)}
        >
          <option value="Text">Text</option>
          <option value="File">File</option>
        </select>
      </label>
    </BaseNode>
  );
};
