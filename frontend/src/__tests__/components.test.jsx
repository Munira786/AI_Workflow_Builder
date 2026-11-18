import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Toolbar } from '../Toolbar';
import { RunPanel } from '../RunPanel';
import { ErrorBoundary } from '../ErrorBoundary';
import { useStore } from '../store';
import { indexByType } from '../catalog';
import { CATALOG } from './fixtures';

const textNode = { id: 'text-1', type: 'text', position: { x: 0, y: 0 }, data: {} };

beforeEach(() => {
  useStore.getState().newPipeline();
  useStore.setState({ catalog: CATALOG, specs: indexByType(CATALOG) });
});

describe('Toolbar', () => {
  it('lists every catalogue node and disables the ones that cannot run (C18)', () => {
    render(<Toolbar />);
    expect(screen.getByText('LLM')).toHaveAttribute('draggable', 'true');
    const email = screen.getByText('Email').closest('.palette-item');
    expect(email).toHaveAttribute('aria-disabled', 'true');
    expect(email).not.toHaveAttribute('draggable');
  });
});

describe('RunPanel', () => {
  it('shows one field per effective input name', () => {
    useStore.setState({
      nodes: [
        { id: 'customInput-1', type: 'customInput', position: { x: 0, y: 0 }, data: { inputName: '' } },
        { id: 'customInput-2', type: 'customInput', position: { x: 0, y: 0 }, data: { inputName: 'topic' } },
      ],
    });
    render(<RunPanel />);
    expect(screen.getByLabelText('input_1')).toBeInTheDocument();
    expect(screen.getByLabelText('topic')).toBeInTheDocument();
  });

  it('disables Run while a run is being followed', () => {
    useStore.setState({ nodes: [textNode], polling: true });
    render(<RunPanel />);
    expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled();
  });

  it('shows outputs and token usage of a finished run', () => {
    useStore.setState({
      nodes: [textNode],
      run: {
        id: 'r', status: 'succeeded', outputs: { poem: 'Autumn' }, node_states: {},
        error: null, input_tokens: 10, output_tokens: 5,
      },
    });
    render(<RunPanel />);
    expect(screen.getByText('Autumn')).toBeInTheDocument();
    expect(screen.getByText(/10 in \/ 5 out tokens/)).toBeInTheDocument();
  });
});

describe('ErrorBoundary', () => {
  it('shows a recovery screen instead of a blank page', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    let explode = true;
    const Bomb = () => {
      if (explode) throw new Error('kaboom');
      return <span>recovered</span>;
    };
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('kaboom');
    explode = false;
    await userEvent.click(screen.getByRole('button', { name: 'Try to continue' }));
    expect(screen.getByText('recovered')).toBeInTheDocument();
    spy.mockRestore();
  });
});
