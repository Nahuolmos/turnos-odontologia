import { formatHora } from '@/shared/format/date-time';
import type { Slot } from '../types';

interface SlotStepProps {
  fecha: string;
  slots: Slot[];
  cargando: boolean;
  error: string | null;
  onFechaChange: (fecha: string) => void;
  onBuscar: () => void;
  onSelect: (slot: Slot) => void;
  onVolver: () => void;
}

export default function SlotStep({
  fecha,
  slots,
  cargando,
  error,
  onFechaChange,
  onBuscar,
  onSelect,
  onVolver,
}: SlotStepProps) {
  return (
    <div className="booking-step" data-testid="slot-step">
      <fieldset>
        <legend>Horario</legend>

        <div className="slot-search">
          <div className="form-field">
            <label htmlFor="fecha-turno">Fecha del turno</label>
            <input
              type="date"
              id="fecha-turno"
              className="form-input"
              value={fecha}
              onChange={(event) => onFechaChange(event.target.value)}
            />
          </div>
          <button type="button" className="btn btn-primary" onClick={onBuscar} disabled={cargando}>
            Buscar horarios
          </button>
        </div>

        {cargando && <p className="booking-status">Buscando horarios disponibles…</p>}

        {!cargando && slots.length === 0 && !error && (
          <p className="booking-status">Seleccioná una fecha y buscá horarios disponibles.</p>
        )}

        {slots.length > 0 && (
          <div className="slots-grid" data-testid="slots-grid">
            {slots.map((slot) => (
              <button
                key={`${slot.inicio}-${slot.sillon_id}`}
                type="button"
                className="slot-button"
                aria-label={`Elegir horario ${formatHora(slot.inicio)}`}
                onClick={() => onSelect(slot)}
              >
                {formatHora(slot.inicio)}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="booking-alert" role="alert">
            {error}
          </div>
        )}

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={onVolver}>
            Volver
          </button>
        </div>
      </fieldset>
    </div>
  );
}
