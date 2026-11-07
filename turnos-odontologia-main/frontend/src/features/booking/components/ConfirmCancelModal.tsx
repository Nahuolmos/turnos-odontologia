import { useEffect, useRef } from 'react';

interface ConfirmCancelModalProps {
  retieneSena: boolean;
  cancelando: boolean;
  onVolver: () => void;
  onConfirmar: () => void;
}

export default function ConfirmCancelModal({
  retieneSena,
  cancelando,
  onVolver,
  onConfirmar,
}: ConfirmCancelModalProps) {
  const volverRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    volverRef.current?.focus();
  }, []);

  useEffect(() => {
    const manejarTecla = (event: KeyboardEvent): void => {
      if (event.key === 'Escape' && !cancelando) {
        onVolver();
      }
    };
    document.addEventListener('keydown', manejarTecla);
    return () => {
      document.removeEventListener('keydown', manejarTecla);
    };
  }, [cancelando, onVolver]);

  return (
    <div className="manage-modal-backdrop" onClick={onVolver}>
      <div
        className="manage-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cancel-modal-title"
        aria-describedby="cancel-modal-description"
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        <h2 id="cancel-modal-title">Cancelar turno</h2>
        <p id="cancel-modal-description">
          {retieneSena
            ? 'Faltan menos de 12 horas para el turno: la seña abonada quedará retenida. El horario se libera igual.'
            : 'La cancelación está en término: no se retiene la seña y vas a liberar el horario para otro paciente.'}
        </p>
        <div className="manage-modal-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onVolver}
            ref={volverRef}
            disabled={cancelando}
          >
            Volver
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={onConfirmar}
            disabled={cancelando}
          >
            {cancelando ? 'Cancelando…' : 'Confirmar cancelación'}
          </button>
        </div>
      </div>
    </div>
  );
}
