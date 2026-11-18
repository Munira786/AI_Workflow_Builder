import { useEffect, useMemo } from 'react';
import { useUpdateNodeInternals } from 'reactflow';
import { useStore } from '../store';
import { templateVariables } from '../catalog';
import { BaseNode } from './BaseNode';

export const TextNode = ({ id, type, data }) => {
  const spec = useStore((state) => state.specs[type]);
  const pattern = useStore((state) => state.catalog.template_variable_pattern);
  const updateNodeField = useStore((state) => state.updateNodeField);
  const updateNodeInternals = useUpdateNodeInternals();
  const text = data?.text ?? spec.default_data.text ?? '';

  // Each unique {{variable}} becomes an input handle.
  const variables = useMemo(() => templateVariables(pattern, text), [pattern, text]);
  const variablesKey = variables.join(',');

  // Refresh React Flow's handle positions when the set of variables changes.
  useEffect(() => {
    updateNodeInternals(id);
  }, [variablesKey, id, updateNodeInternals]);

  // Grow the node with its content.
  const lines = text.split('\n');
  const longestLine = Math.max(...lines.map((line) => line.length));
  const width = Math.min(500, Math.max(250, longestLine * 8));
  const minHeight = Math.max(120, 80 + lines.length * 25, 60 + variables.length * 30);

  return (
    <BaseNode id={id} spec={spec} inputs={variables} width={width} minHeight={minHeight}>
      <textarea
        aria-label="Text template"
        className="input textarea nodrag"
        value={text}
        placeholder="Type text; use {{name}} to add an input"
        onChange={(e) => updateNodeField(id, 'text', e.target.value)}
      />
      {variables.length > 0 && <span className="hint">Inputs: {variables.join(', ')}</span>}
    </BaseNode>
  );
};
