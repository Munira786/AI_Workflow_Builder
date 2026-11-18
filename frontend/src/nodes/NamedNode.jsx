// Input and Output nodes: a user-facing name (used as the run-input key / output name).

import { useStore } from '../store';
import { defaultName } from '../catalog';
import { BaseNode } from './BaseNode';

export const NamedNode = ({ id, type, data }) => {
  const spec = useStore((state) => state.specs[type]);
  const updateNodeField = useStore((state) => state.updateNodeField);
  const fallback = defaultName(spec, id);

  return (
    <BaseNode id={id} spec={spec}>
      <label className="field field--inline">
        Name
        <input
          type="text"
          className="input input--small nodrag"
          value={data?.[spec.name_field] ?? ''}
          placeholder={fallback}
          onChange={(e) => updateNodeField(id, spec.name_field, e.target.value)}
          onBlur={(e) => {
            // A blank name would silently fall back to the default; show that explicitly.
            if (!e.target.value.trim()) updateNodeField(id, spec.name_field, fallback);
          }}
        />
      </label>
      <span className="hint">{spec.description}</span>
    </BaseNode>
  );
};
