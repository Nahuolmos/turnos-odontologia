import { useState } from 'react';
import { formatHora, todayIso } from '@/shared/format/date-time';
import type { Slot, TurnoGestion } from '../types';

interface ReprogramFormProps {
  turno: TurnoGestion;
  slots: Slot[];
  cargandoSlots: boolean;
  reprogramando: boolean;
  onBuscar: (fecha: string) => void;
  onReprogramar: (slot: Slot) => void;
  onVolver: () => void;
}

export default function ReprogramForm({
  turno,
  slots,
  cargandoSlots,
  reprogramando,
  onBuscar,
  onReprogramar,
  onVolver,
}: ReprogramFormProps) {
  const [fecha, setFecha] = useState(todayIso());
  const [slotElegido, setSlotElegido] = useState<Slot | null>(null);

  const buscar = () => {
    setSlotElegido(null);
    onBuscar(fecha);
  };

  const confirmar = () => {
    if (slotElegido) {
      onReprogramar(slotElegido);
    }
  };

  return (
    <section className="manage-card" data-testid="reprogram-form" aria-labelledby="reprogram-title">
      <h2 id="reprogram-title">Elegí un nuevo horario</h2>

      {!turno.puede_reprogramar_sin_sena && (
        <p className="manage-hint">
          Esta reprogramación requiere abonar una nueva seña. El turno actual quedará cancelado.
        </p>
      )}

      <div className="manage-search">
        <div className="form-group">
          <label htmlFor="nueva-fecha">Nueva fecha</label>
          <input
            type="date"
            id="nueva-fecha"
            className="form-input"
            value={fecha}
            onChange={(event) => setFecha(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={buscar}
          disabled={cargandoSlots}
        >
          Buscar horarios
        </button>
      </div>

      {cargandoSlots && <p className="manage-status">Buscando horarios disponibles…</p>}

      {!cargandoSlots && slots.length === 0 && (
        <p className="manage-status">
          Elegí una fecha y buscá horarios disponibles para reprogramar.
        </p>
      )}

      {slots.length > 0 && (
        <div className="manage-slots" data-testid="manage-slots">
          {slots.map((slot) => {
            const elegido =
              slotElegido?.inicio === slot.inicio && slotElegido.sillon_id === slot.sillon_id;
            return (
              <button
                key={`${slot.inicio}-${slot.sillon_id}`}
                type="button"
                className={`manage-slot ${elegido ? 'manage-slot--elegido' : ''}`}
                aria-label={`Elegir horario ${formatHora(slot.inicio)}`}
                aria-pressed={elegido}
                onClick={() => setSlotElegido(slot)}
              >
                {formatHora(slot.inicio)}
              </button>
            );
          })}
        </div>
      )}

      <div className="manage-actions manage-actions--form">
        <button type="button" className="btn btn-secondary" onClick={onVolver}>
          Volver
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={confirmar}
          disabled={!slotElegido || reprogramando}
        >
          {reprogramando ? 'Reprogramando…' : 'Confirmar reprogramación'}
        </button>
      </div>
    </section>
  );
}
