// Node types that need custom UI. Every other type in the backend catalogue renders with
// GenericNode, so adding a node usually needs no frontend change at all.

import { GenericNode } from './GenericNode';
import { LLMNode } from './LLMNode';
import { NamedNode } from './NamedNode';
import { TextNode } from './TextNode';

const CUSTOM_COMPONENTS = {
  customInput: NamedNode,
  customOutput: NamedNode,
  text: TextNode,
  llm: LLMNode,
};

export const componentFor = (type) => CUSTOM_COMPONENTS[type] || GenericNode;

/** React Flow `nodeTypes` for every type in the catalogue. */
export const buildNodeTypes = (catalog) =>
  Object.fromEntries(catalog.node_types.map((spec) => [spec.type, componentFor(spec.type)]));
