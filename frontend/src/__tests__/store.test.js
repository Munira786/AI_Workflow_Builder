import { act } from '@testing-library/react';
import { MAX_POLL_FAILURES, POLL_INTERVAL_MS, useStore } from '../store';
import { indexByType } from '../catalog';
import { CATALOG, mockFetch } from './fixtures';

const isPost = (path) => (url, opts) => url.endsWith(path) && opts.method === 'POST';
const isGet = (path) => (url, opts) => url.endsWith(path) && (opts.method || 'GET') === 'GET';

const runRow = (status, extra = {}) => ({
  id: 'r1',
  status,
  outputs: {},
  node_states: {},
  error: null,
  input_tokens: 0,
  output_tokens: 0,
  ...extra,
});

const advance = async (ms = 0) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

beforeEach(() => {
  vi.useFakeTimers();
  useStore.getState().newPipeline();
  useStore.setState({ catalog: CATALOG, specs: indexByType(CATALOG) });
  useStore.getState().addNodeOfType('text', { x: 0, y: 0 });
});

afterEach(() => {
  useStore.getState().stopFollowingRun();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('run polling', () => {
  it('follows a run until it finishes', async () => {
    let calls = 0;
    vi.stubGlobal('fetch', mockFetch([
      [isPost('/runs'), { status: 202, body: runRow('queued') }],
      [isGet('/runs/r1'), () => {
        calls += 1;
        return { body: runRow(calls < 2 ? 'running' : 'succeeded', { node_states: { 'text-1': { status: 'succeeded' } } }) };
      }],
    ]));
    await act(() => useStore.getState().startRun({}));
    await advance(0);
    expect(useStore.getState().polling).toBe(true);
    await advance(POLL_INTERVAL_MS);
    const state = useStore.getState();
    expect(state.run.status).toBe('succeeded');
    expect(state.polling).toBe(false);
    expect(state.nodeStatuses['text-1'].status).toBe('succeeded');
  });

  it('keeps polling through a transient error instead of freezing (C5)', async () => {
    let calls = 0;
    vi.stubGlobal('fetch', mockFetch([
      [isPost('/runs'), { status: 202, body: runRow('queued') }],
      [isGet('/runs/r1'), () => {
        calls += 1;
        return calls === 1 ? new TypeError('network down') : { body: runRow('succeeded') };
      }],
    ]));
    await act(() => useStore.getState().startRun({}));
    await advance(0);
    expect(useStore.getState().runError).toMatch(/retrying/);
    expect(useStore.getState().polling).toBe(true);
    await advance(POLL_INTERVAL_MS * 2); // first backoff step
    expect(useStore.getState().run.status).toBe('succeeded');
    expect(useStore.getState().polling).toBe(false);
    expect(useStore.getState().runError).toBe('');
  });

  it('gives up after repeated failures and re-enables the Run button', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [isPost('/runs'), { status: 202, body: runRow('queued') }],
      [isGet('/runs/r1'), () => new TypeError('network down')],
    ]));
    await act(() => useStore.getState().startRun({}));
    await advance(0);
    for (let attempt = 1; attempt < MAX_POLL_FAILURES; attempt += 1) {
      await advance(POLL_INTERVAL_MS * 2 ** attempt);
    }
    expect(useStore.getState().polling).toBe(false);
    expect(useStore.getState().runError).toMatch(/Stopped following/);
  });

  it('stops painting statuses after another pipeline is opened (C9)', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [isPost('/runs'), { status: 202, body: runRow('queued') }],
      [isGet('/runs/r1'), { body: runRow('running', { node_states: { 'text-1': { status: 'running' } } }) }],
    ]));
    await act(() => useStore.getState().startRun({}));
    await advance(0);
    act(() => useStore.getState().loadPipeline({ id: 'p2', name: 'Other', graph: { nodes: [], edges: [] } }));
    await advance(POLL_INTERVAL_MS * 5);
    const state = useStore.getState();
    expect(state.nodeStatuses).toEqual({});
    expect(state.run).toBeNull();
    expect(state.polling).toBe(false);
  });

  it('clears stale statuses when the graph is edited after a run (C9)', () => {
    useStore.setState({ nodeStatuses: { 'text-1': { status: 'succeeded' } }, polling: false });
    useStore.getState().updateNodeField('text-1', 'text', 'changed');
    expect(useStore.getState().nodeStatuses).toEqual({});
  });
});

describe('canvas', () => {
  it('creates nodes from the catalogue with default data and unique ids', () => {
    useStore.getState().addNodeOfType('customInput', { x: 0, y: 0 });
    useStore.getState().addNodeOfType('customInput', { x: 0, y: 0 });
    const inputs = useStore.getState().nodes.filter((node) => node.type === 'customInput');
    expect(inputs.map((node) => node.id)).toEqual(['customInput-1', 'customInput-2']);
    expect(inputs[1].data).toEqual({ inputName: 'input_2' });
    expect(useStore.getState().nodes[0].data).toEqual({ text: '{{input}}' });
  });
});
