// styles.js
// Shared inline style helpers so buttons and inputs look the same everywhere.

export const inputStyle = {
  padding: '8px 10px',
  border: '1px solid #d1d5db',
  borderRadius: 8,
  fontSize: 14,
  fontFamily: 'inherit',
};

const variants = {
  primary: { background: '#2563eb', color: '#fff', border: '1px solid #2563eb' },
  secondary: { background: '#fff', color: '#111827', border: '1px solid #d1d5db' },
  danger: { background: '#fff', color: '#b91c1c', border: '1px solid #fca5a5' },
  ghost: { background: 'transparent', color: '#2563eb', border: '1px solid transparent' },
};

export const buttonStyle = (variant = 'secondary') => ({
  ...variants[variant],
  padding: '8px 16px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
});

export const STATUS_COLORS = {
  pending: '#9ca3af',
  queued: '#9ca3af',
  running: '#f59e0b',
  succeeded: '#16a34a',
  failed: '#dc2626',
};
