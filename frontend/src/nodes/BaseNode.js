import React from 'react';
import { Handle } from 'reactflow';
import { useStore } from '../store';
import { STATUS_COLORS } from '../styles';

export const BaseNode = ({
  id,
  title,
  children,
  handles = [],
  width = 220,
  minHeight = 100,
}) => {
  const runState = useStore((state) => state.nodeStatuses[id]);
  const statusColor = runState ? STATUS_COLORS[runState.status] : null;

  return (
    <div
      style={{
        width,
        minHeight,
        boxSizing: 'border-box',
        border: statusColor ? `2px solid ${statusColor}` : '1px solid #d1d5db',
        borderRadius: '14px',
        padding: '16px',
        background: '#ffffff',
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        fontFamily: 'Inter, Arial, sans-serif',
      }}
    >
      {handles.map((handle) => (
        <Handle
          key={handle.id}
          type={handle.type}
          position={handle.position}
          id={handle.id}
          title={handle.label}
          style={{
            width: 12,
            height: 12,
            background: '#2563eb',
            border: '2px solid white',
            ...handle.style,
          }}
        />
      ))}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '18px',
          fontWeight: 600,
          marginBottom: '12px',
          color: '#111827',
        }}
      >
        {title}
        {runState && (
          <span style={{ fontSize: 12, fontWeight: 600, color: statusColor }}>{runState.status}</span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 14 }}>
        {children}
      </div>

      {runState?.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: STATUS_COLORS.failed }}>{runState.error}</div>
      )}
    </div>
  );
};
