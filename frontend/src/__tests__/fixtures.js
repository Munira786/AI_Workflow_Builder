// A catalogue shaped like GET /api/v1/node-types.
const spec = (overrides) => ({
  inputs: [],
  outputs: [],
  executable: true,
  dynamic_inputs: false,
  name_field: null,
  name_prefix: null,
  default_data: {},
  ...overrides,
});

export const CATALOG = {
  template_variable_pattern: '{{\\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\\s*}}',
  default_model: 'claude-opus-5-5',
  allowed_models: ['claude-opus-5-5'],
  node_types: [
    spec({ type: 'customInput', label: 'Input', description: 'A value.', outputs: ['value'], name_field: 'inputName', name_prefix: 'input_' }),
    spec({ type: 'llm', label: 'LLM', description: 'Calls Claude.', inputs: ['system', 'prompt'], outputs: ['response'] }),
    spec({ type: 'customOutput', label: 'Output', description: 'A result.', inputs: ['value'], name_field: 'outputName', name_prefix: 'output_' }),
    spec({ type: 'text', label: 'Text', description: 'A template.', outputs: ['output'], dynamic_inputs: true, default_data: { text: '{{input}}' } }),
    spec({ type: 'email', label: 'Email', description: 'Send an email.', executable: false, inputs: ['message'], outputs: ['sent'] }),
  ],
};

/** A fetch stub answering from [matcher, response] pairs; the first matching route wins. */
export const mockFetch = (routes) =>
  vi.fn(async (url, options = {}) => {
    const route = routes.find(([match]) => match(url, options));
    if (!route) throw new Error(`Unexpected request: ${options.method || 'GET'} ${url}`);
    const result = typeof route[1] === 'function' ? route[1](url, options) : route[1];
    if (result instanceof Error) throw result;
    const { status = 200, body = {}, headers = {} } = result;
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: { get: (name) => headers[name] ?? null },
      json: async () => body,
    };
  });
