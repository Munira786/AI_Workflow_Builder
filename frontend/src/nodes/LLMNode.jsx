import { useStore } from '../store';
import { BaseNode } from './BaseNode';

export const LLMNode = ({ id, type, data }) => {
  const spec = useStore((state) => state.specs[type]);
  const { default_model: defaultModel, allowed_models: models } = useStore((state) => state.catalog);
  const updateNodeField = useStore((state) => state.updateNodeField);

  return (
    <BaseNode id={id} spec={spec}>
      <span>Calls Claude with a prompt.</span>
      {models.length > 1 && (
        <label className="field field--inline">
          Model
          <select
            className="input input--small nodrag"
            value={data?.model || defaultModel}
            onChange={(e) => updateNodeField(id, 'model', e.target.value)}
          >
            {models.map((model) => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </label>
      )}
      <span className="hint">Inputs: system (optional), prompt → response</span>
    </BaseNode>
  );
};
