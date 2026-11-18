// Draggable node palette, built from the backend's node catalogue.

import { useStore } from './store';

export const DRAG_MIME = 'application/reactflow';

export const Toolbar = () => {
  const catalog = useStore((state) => state.catalog);

  const onDragStart = (event, type) => {
    event.dataTransfer.setData(DRAG_MIME, JSON.stringify({ nodeType: type }));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="toolbar" role="toolbar" aria-label="Nodes">
      {catalog.node_types.map((spec) =>
        spec.executable ? (
          <div
            key={spec.type}
            className="palette-item"
            draggable
            onDragStart={(event) => onDragStart(event, spec.type)}
            title={spec.description}
          >
            {spec.label}
          </div>
        ) : (
          <div
            key={spec.type}
            className="palette-item palette-item--disabled"
            aria-disabled="true"
            title={`${spec.description} Coming soon.`}
          >
            {spec.label}
            <span className="palette-item__badge">soon</span>
          </div>
        ),
      )}
    </div>
  );
};
