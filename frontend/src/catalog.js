// Helpers over the node catalogue served by GET /api/v1/node-types.
// The backend's registry (app/engine/registry.py) is the source of truth for node types,
// handles, default data, naming and the template-variable syntax; nothing here hard-codes them.

const HANDLE_SEPARATOR = '-';

export const handleId = (nodeId, handle) => `${nodeId}${HANDLE_SEPARATOR}${handle}`;

/** Default name for an input/output node: name_prefix + trailing number of the id.
 *  Mirrors registry.default_name() on the backend. */
export const defaultName = (spec, nodeId) => {
  const match = /(\d+)$/.exec(nodeId);
  return `${spec.name_prefix}${match ? match[1] : nodeId}`;
};

/** The name the backend will use: the node's own name, or the default when blank. */
export const effectiveName = (spec, node) => {
  const value = node.data?.[spec.name_field];
  return typeof value === 'string' && value.trim() ? value.trim() : defaultName(spec, node.id);
};

/** Unique {{variables}} in a template, in order of appearance. */
export const templateVariables = (pattern, text) => {
  const regex = new RegExp(pattern, 'g');
  return [...new Set([...(text || '').matchAll(regex)].map((match) => match[1]))];
};

/** Data for a freshly dropped node: the spec's defaults plus a default name if it has one. */
export const initialData = (spec, nodeId) => {
  const data = { ...spec.default_data };
  if (spec.name_field) data[spec.name_field] = defaultName(spec, nodeId);
  return data;
};

export const indexByType = (catalog) =>
  Object.fromEntries((catalog?.node_types || []).map((spec) => [spec.type, spec]));
