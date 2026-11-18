import { Handle, Position } from 'reactflow';
import { useStore } from '../store';
import { handleId } from '../catalog';

const spread = (index, count) => `${((index + 1) * 100) / (count + 1)}%`;

/** Shared node frame: title, run status, and handles derived from the catalogue spec. */
export const BaseNode = ({ id, spec, inputs = spec.inputs, children, width = 220, minHeight = 100 }) => {
  const runState = useStore((state) => state.nodeStatuses[id]);
  const status = runState?.status;

  return (
    <div
      className={`node${status ? ` node--${status}` : ''}`}
      style={{ width, minHeight }}
      data-testid={`node-${id}`}
    >
      {inputs.map((name, index) => (
        <Handle
          key={`in-${name}`}
          type="target"
          position={Position.Left}
          id={handleId(id, name)}
          title={name}
          className="node__handle"
          style={{ top: spread(index, inputs.length) }}
        />
      ))}
      {spec.outputs.map((name, index) => (
        <Handle
          key={`out-${name}`}
          type="source"
          position={Position.Right}
          id={handleId(id, name)}
          title={name}
          className="node__handle"
          style={{ top: spread(index, spec.outputs.length) }}
        />
      ))}

      <div className="node__title">
        {spec.label}
        {status && <span className={`node__status status-${status}`}>{status}</span>}
      </div>

      <div className="node__body">{children}</div>

      {runState?.error && <div className="node__error">{runState.error}</div>}
    </div>
  );
};
