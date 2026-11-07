import { useState, type FormEvent } from 'react';
import { formatFecha, formatHora, formatPrecio } from '@/shared/format/date-time';
import type { Slot, TipoPractica } from '../types';

const TELEFONO_VALIDO = /^\+?[1-9]\d{7,14}$/;

interface PatientStepProps {
  slot: Slot;
  practica: TipoPractica | undefined;
  enviando: boolean;
  error: string | null;
  onConfirmar: (nombre: string, telefono: string) => Promise<boolean>;
  onVolver: () => void;
}

export default function PatientStep({
  slot,
  practica,
  enviando,
  error,
  onConfirmar,
  onVolver,
}: PatientStepProps) {
  const [nombre, setNombre] = useState('');
  const [telefono, setTelefono] = useState('');
  const [errorLocal, setErrorLocal] = useState<string | null>(null);

  const confirmar = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorLocal(null);

    if (nombre.trim() === '') {
      setErrorLocal('Ingresá tu nombre y apellido.');
      return;
    }
    if (!TELEFONO_VALIDO.test(telefono.trim())) {
      setErrorLocal('Ingresá un teléfono válido (8 a 15 dígitos, puede incluir +).');
      return;
    }

    await onConfirmar(nombre.trim(), telefono.trim());
  };

  return (
    <div className="booking-step" data-testid="patient-step">
      <fieldset>
        <legend>Datos</legend>

        <div className="booking-summary">
          <strong>{practica?.nombre ?? 'Práctica seleccionada'}</strong>
          <span>
            {formatFecha(slot.inicio)} a las {formatHora(slot.inicio)}
          </span>
          {practica && <span>Seña estimada: {formatPrecio(practica.precio_base * practica.sena_pct / 100)}</span>}
        </div>

        <form className="booking-patient-form" onSubmit={(event) => void confirmar(event)}>
          <div className="form-field">
            <label htmlFor="nombre">Nombre y apellido</label>
            <input
              type="text"
              id="nombre"
              className="form-input"
              value={nombre}
              onChange={(event) => setNombre(event.target.value)}
              autoComplete="name"
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="telefono">Teléfono</label>
            <input
              type="tel"
              id="telefono"
              className="form-input"
              placeholder="+5491112345678"
              value={telefono}
              onChange={(event) => setTelefono(event.target.value)}
              autoComplete="tel"
              required
            />
            <small className="field-hint">Con código de área, por ejemplo +5491112345678.</small>
          </div>

          {(errorLocal ?? error) && (
            <div className="booking-alert" role="alert">
              <p>{errorLocal ?? error}</p>
              {error && !errorLocal && (
                <button type="button" className="btn btn-secondary" onClick={onVolver}>
                  Volver a elegir horario
                </button>
              )}
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onVolver}>
              Volver
            </button>
            <button type="submit" className="btn btn-primary" disabled={enviando}>
              {enviando ? 'Confirmando…' : 'Confirmar reserva'}
            </button>
          </div>
        </form>
      </fieldset>
    </div>
  );
}
