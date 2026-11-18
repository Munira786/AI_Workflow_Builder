// Display helpers for timestamps, durations and token counts.

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

const UNITS = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
];

/** "just now", "5 minutes ago", "yesterday", ... */
export const formatRelative = (iso, now = Date.now()) => {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  if (Math.abs(seconds) < 45) return 'just now';
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size || unit === 'minute') {
      return relative.format(Math.round(seconds / size), unit);
    }
  }
  return 'just now';
};

export const formatDateTime = (iso) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' });

/** "850 ms", "4.2 s", "3 min 05 s"; null when the run hasn't finished. */
export const formatDuration = (startIso, endIso) => {
  if (!startIso || !endIso) return null;
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (ms < 1000) return `${Math.max(ms, 0)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes} min ${String(seconds).padStart(2, '0')} s`;
};

export const formatTokens = (run) => {
  const total = (run.input_tokens || 0) + (run.output_tokens || 0);
  if (!total) return null;
  return `${run.input_tokens.toLocaleString()} in / ${run.output_tokens.toLocaleString()} out tokens`;
};
