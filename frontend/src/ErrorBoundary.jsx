import { Component } from 'react';

/** Catches render errors so one broken component shows a message instead of a blank page. */
export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="error-page">
        <h1>Something went wrong</h1>
        <p>The editor hit an unexpected error. Unsaved changes may be lost.</p>
        <pre className="error-page__detail">{String(this.state.error.message || this.state.error)}</pre>
        <div className="row">
          <button type="button" className="btn btn--primary" onClick={() => window.location.reload()}>
            Reload
          </button>
          <button type="button" className="btn" onClick={() => this.setState({ error: null })}>
            Try to continue
          </button>
        </div>
      </div>
    );
  }
}
