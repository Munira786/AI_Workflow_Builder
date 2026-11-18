import { defaultName, effectiveName, handleId, indexByType, initialData, templateVariables } from '../catalog';
import { CATALOG } from './fixtures';

const specs = indexByType(CATALOG);

describe('catalog helpers', () => {
  it('builds default names like the backend (registry.default_name)', () => {
    expect(defaultName(specs.customInput, 'customInput-3')).toBe('input_3');
    expect(defaultName(specs.customOutput, 'customOutput-12')).toBe('output_12');
    expect(defaultName(specs.customInput, 'weird')).toBe('input_weird');
  });

  it('falls back to the default name when the name is blank (C7)', () => {
    const node = (inputName) => ({ id: 'customInput-1', data: { inputName } });
    expect(effectiveName(specs.customInput, node('topic'))).toBe('topic');
    expect(effectiveName(specs.customInput, node('  '))).toBe('input_1');
    expect(effectiveName(specs.customInput, node(undefined))).toBe('input_1');
  });

  it('extracts unique template variables with the backend pattern', () => {
    const pattern = CATALOG.template_variable_pattern;
    expect(templateVariables(pattern, 'Hi {{ name }}, {{name}} and {{x_1}}')).toEqual(['name', 'x_1']);
    expect(templateVariables(pattern, 'no vars {{ 1bad }}')).toEqual([]);
  });

  it('starts new nodes with the spec defaults and an explicit name', () => {
    expect(initialData(specs.text, 'text-1')).toEqual({ text: '{{input}}' });
    expect(initialData(specs.customInput, 'customInput-2')).toEqual({ inputName: 'input_2' });
  });

  it('names handles <node id>-<handle>', () => {
    expect(handleId('llm-1', 'prompt')).toBe('llm-1-prompt');
  });
});
