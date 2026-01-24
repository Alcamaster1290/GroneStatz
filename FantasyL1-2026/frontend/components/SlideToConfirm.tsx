"use client";

import { useEffect, useState } from "react";

export default function SlideToConfirm({
  onConfirm,
  disabled
}: {
  onConfirm: () => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (value >= 100 && !disabled) {
      onConfirm();
      setValue(0);
    }
  }, [value, disabled, onConfirm]);

  return (
    <div className="glass rounded-2xl p-4">
      <p className="text-xs text-muted">Desliza para confirmar</p>
      <input
        type="range"
        min={0}
        max={100}
        value={value}
        onChange={(event) => setValue(Number(event.target.value))}
        disabled={disabled}
        className="mt-3 w-full"
      />
    </div>
  );
}
