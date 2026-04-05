import React from 'react';

export default function Badge({ label, color }) {
  return (
    <span
      style={{
        background: `${color}22`,
        color,
        border: `1px solid ${color}44`,
        borderRadius: 4,
        padding: '2px 7px',
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: 0.5,
        textTransform: 'uppercase',
      }}
    >
      {label}
    </span>
  );
}
