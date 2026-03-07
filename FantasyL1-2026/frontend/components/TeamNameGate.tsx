"use client";

type TeamNameGateProps = {
  open: boolean;
  teamName: string;
  onTeamNameChange: (value: string) => void;
  onSave: () => void;
  onClose?: () => void;
  error?: string | null;
};

export default function TeamNameGate({
  open,
  teamName,
  onTeamNameChange,
  onSave,
  onClose,
  error
}: TeamNameGateProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
      <div className="ui-panel w-full max-w-sm space-y-4 rounded-2xl p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ink">Nombre del equipo</p>
            <p className="mt-1 text-xs text-muted">
              Debes nombrar tu equipo antes de continuar.
            </p>
          </div>
          {onClose ? (
            <button
              onClick={onClose}
              aria-label="Cerrar"
              className="ui-btn ui-btn-secondary px-2 py-1 text-xs"
            >
              Cerrar
            </button>
          ) : null}
        </div>
        <div className="space-y-2">
          <label className="text-xs text-muted">Nombre del equipo</label>
          <input
            value={teamName}
            onChange={(event) => onTeamNameChange(event.target.value)}
            className="ui-input px-3 py-2 text-sm"
            placeholder="Ej: Los Grones"
          />
          {error ? <p className="text-xs text-warning">{error}</p> : null}
        </div>
        <button
          onClick={onSave}
          className="ui-btn ui-btn-primary w-full px-4 py-2 text-sm"
        >
          Guardar nombre
        </button>
      </div>
    </div>
  );
}
