import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RunHistory } from '../RunHistory';
import { HISTORY_PAGE_SIZE, useStore } from '../store';
import { indexByType } from '../catalog';
import { formatDuration, formatRelative } from '../format';
import { CATALOG, mockFetch } from './fixtures';

const run = (id, overrides = {}) => ({
  id,
  pipeline_id: 'p1',
  pipeline_name: 'Greeter',
  status: 'succeeded',
  inputs: { who: 'Ada' },
  outputs: { greeting: `Hello Ada (${id})` },
  node_states: { 'customInput-1': { status: 'succeeded' }, 'text-9': { status: 'skipped' } },
  error: null,
  input_tokens: 0,
  output_tokens: 0,
  created_at: '2026-11-18T10:00:00Z',
  started_at: '2026-11-18T10:00:00Z',
  finished_at: '2026-11-18T10:00:01.500Z',
  ...overrides,
});

const pipeline = {
  id: 'p1',
  name: 'Greeter',
  graph: {
    nodes: [{ id: 'customInput-1', type: 'customInput', position: { x: 0, y: 0 }, data: { inputName: 'who' } }],
    edges: [],
  },
};

const settle = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

beforeEach(() => {
  useStore.getState().resetSession();
  useStore.setState({ catalog: CATALOG, specs: indexByType(CATALOG) });
});

afterEach(() => {
  useStore.getState().stopFollowingRun();
  vi.unstubAllGlobals();
});

describe('format helpers', () => {
  it('formats relative times and durations', () => {
    const now = Date.parse('2026-11-18T10:10:00Z');
    expect(formatRelative('2026-11-18T10:09:50Z', now)).toBe('just now');
    expect(formatRelative('2026-11-18T10:05:00Z', now)).toMatch(/5 minutes ago/);
    expect(formatDuration('2026-11-18T10:00:00Z', '2026-11-18T10:00:00.850Z')).toBe('850 ms');
    expect(formatDuration('2026-11-18T10:00:00Z', '2026-11-18T10:03:05Z')).toBe('3 min 05 s');
    expect(formatDuration('2026-11-18T10:00:00Z', null)).toBeNull();
  });
});

describe('history store', () => {
  it('loads the open pipeline’s runs and pages with the cursor', async () => {
    const fetch = mockFetch([
      [(url) => url.includes('cursor=c1'), { body: { items: [run('r3')], next_cursor: null } }],
      [(url) => url.includes('/runs?'), { body: { items: [run('r1'), run('r2')], next_cursor: 'c1' } }],
    ]);
    vi.stubGlobal('fetch', fetch);
    useStore.getState().loadPipeline(pipeline);
    await useStore.getState().loadHistory();

    expect(fetch.mock.calls[0][0]).toContain(`limit=${HISTORY_PAGE_SIZE}`);
    expect(fetch.mock.calls[0][0]).toContain('pipeline_id=p1');
    await useStore.getState().loadHistory({ more: true });
    const { history } = useStore.getState();
    expect(history.items.map((r) => r.id)).toEqual(['r1', 'r2', 'r3']);
    expect(history.nextCursor).toBeNull();
  });

  it('shows all runs without a pipeline filter', async () => {
    const fetch = mockFetch([[(url) => url.includes('/runs?'), { body: { items: [], next_cursor: null } }]]);
    vi.stubGlobal('fetch', fetch);
    useStore.getState().loadPipeline(pipeline);
    useStore.getState().setHistoryScope('all');
    await settle();
    expect(fetch.mock.calls.at(-1)[0]).not.toContain('pipeline_id');
  });

  it('ignores a slow response that was overtaken by a newer request', async () => {
    let releaseSlow;
    const slow = new Promise((resolve) => { releaseSlow = resolve; });
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(async () => {
        await slow;
        return { ok: true, status: 200, headers: { get: () => null }, json: async () => ({ items: [run('stale')], next_cursor: null }) };
      })
      .mockImplementation(async () => (
        { ok: true, status: 200, headers: { get: () => null }, json: async () => ({ items: [run('fresh')], next_cursor: null }) }
      )));
    useStore.getState().loadPipeline(pipeline);
    const first = useStore.getState().loadHistory();
    await useStore.getState().loadHistory();
    releaseSlow();
    await first;
    expect(useStore.getState().history.items.map((r) => r.id)).toEqual(['fresh']);
  });

  it('re-runs with a past run’s inputs, only for the open pipeline', async () => {
    const fetch = mockFetch([
      [(url, o) => url.endsWith('/runs') && o.method === 'POST', { status: 202, body: run('new', { status: 'queued' }) }],
      [(url) => url.includes('/runs/new'), { body: run('new') }],
    ]);
    vi.stubGlobal('fetch', fetch);
    useStore.getState().loadPipeline(pipeline);

    useStore.getState().rerunWithInputs(run('old', { pipeline_id: 'other' }));
    expect(fetch).not.toHaveBeenCalled();

    useStore.getState().rerunWithInputs(run('old'));
    await settle();
    const body = JSON.parse(fetch.mock.calls[0][1].body);
    expect(body.inputs).toEqual({ who: 'Ada' });
    expect(body.pipeline_id).toBe('p1');
  });

  it('paints a past run on the canvas without starting anything', () => {
    useStore.getState().loadPipeline(pipeline);
    useStore.getState().showRunOnCanvas(run('r1'));
    expect(useStore.getState().nodeStatuses['customInput-1'].status).toBe('succeeded');
    expect(useStore.getState().run.id).toBe('r1');
  });
});

describe('RunHistory drawer', () => {
  it('lists runs, expands one, and closes with Escape', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [(url) => url.includes('/runs?'), {
        body: {
          items: [run('r1'), run('r2', { status: 'failed', error: 'Node x failed', outputs: {} })],
          next_cursor: 'more',
        },
      }],
    ]));
    useStore.getState().loadPipeline(pipeline);
    render(<RunHistory />);
    act(() => useStore.getState().toggleHistory());
    await settle();

    const drawer = screen.getByRole('complementary', { name: 'Run history' });
    const items = within(drawer).getAllByRole('button', { expanded: false });
    expect(items).toHaveLength(2);
    expect(within(drawer).getByRole('button', { name: 'Load older runs' })).toBeInTheDocument();

    await userEvent.click(items[1]);
    expect(within(drawer).getByText('Node x failed')).toBeInTheDocument();
    expect(within(drawer).getByText('Ada')).toBeInTheDocument();
    expect(within(drawer).getByText(/took 1\.5 s/)).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: 'Run again with these inputs' })).toBeEnabled();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('complementary', { name: 'Run history' })).not.toBeInTheDocument();
  });

  it('offers to open the pipeline for runs of another pipeline', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [(url) => url.includes('/runs?'), { body: { items: [run('r9', { pipeline_id: 'p2', pipeline_name: 'Summariser' })], next_cursor: null } }],
    ]));
    useStore.getState().loadPipeline(pipeline);
    useStore.setState({ historyScope: 'all' });
    render(<RunHistory />);
    act(() => useStore.getState().toggleHistory());
    await settle();

    expect(screen.getByText('Summariser')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { expanded: false }));
    expect(screen.getByRole('button', { name: 'Open “Summariser”' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run again with these inputs' })).not.toBeInTheDocument();
  });

  it('explains why an unsaved pipeline has no history', async () => {
    render(<RunHistory />);
    act(() => useStore.getState().toggleHistory());
    await settle();
    expect(screen.getByText(/Save this pipeline/)).toBeInTheDocument();
  });
});
