import { formatPrecio } from '@/shared/format/date-time';
import type { TipoPractica } from '../types';

interface PracticeStepProps {
  practicas: TipoPractica[];
  seleccionada: string;
  cargando: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onContinuar: () => void;
  onReintentar: () => void;
}

export default function PracticeStep({
  practicas,
  seleccionada,
  cargando,
  error,
  onSelect,
  onContinuar,
  onReintentar,
}: PracticeStepProps) {
  return (
    <div className="booking-step" data-testid="practice-step">
      <fieldset>
        <legend>Tratamiento</legend>

        {cargando && <p className="booking-status">Cargando prácticas…</p>}

        {!cargando && error && (
          <div className="booking-alert" role="alert">
            <p>{error}</p>
            <button type="button" className="btn btn-secondary" onClick={onReintentar}>
              Reintentar
            </button>
          </div>
        )}

        {!cargando && !error && practicas.length === 0 && (
          <p className="booking-status">No hay prácticas disponibles por el momento.</p>
        )}

        <div className="treatment-options">
          {practicas.map((practica) => (
            <label key={practica.id} className="treatment-option">
              <input
                type="radio"
                name="practica"
                value={practica.id}
                checked={seleccionada === practica.id}
                onChange={() => onSelect(practica.id)}
              />
              <span className="treatment-info">
                <strong>{practica.nombre}</strong>
                <small>
                  {practica.duracion_min} min · {formatPrecio(practica.precio_base)} · seña{' '}
                  {practica.sena_pct}%
                </small>
              </span>
            </label>
          ))}
        </div>

        <div className="form-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={seleccionada === ''}
            onClick={onContinuar}
          >
            Continuar
          </button>
        </div>
      </fieldset>
    </div>
  );
}
