import { useStore } from '../store';
import { BaseNode } from './BaseNode';

/** Any node type without custom UI: handles and label come straight from the catalogue. */
export const GenericNode = ({ id, type }) => {
  const spec = useStore((state) => state.specs[type]);
  if (!spec) {
    return (
      <div className="node node--failed" data-testid={`node-${id}`}>
        Unknown node type “{type}”
      </div>
    );
  }
  return (
    <BaseNode id={id} spec={spec}>
      <span>{spec.description}</span>
      {!spec.executable && <span className="hint">Not executable yet</span>}
    </BaseNode>
  );
};
