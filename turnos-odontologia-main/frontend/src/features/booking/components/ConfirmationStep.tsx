import { formatFecha, formatHora, formatPrecio } from '@/shared/format/date-time';
import type { ReservaCreada } from '../types';

interface ConfirmationStepProps {
  reserva: ReservaCreada;
  onReiniciar: () => void;
}

export default function ConfirmationStep({ reserva, onReiniciar }: ConfirmationStepProps) {
  const { turno, manage_token: manageToken } = reserva;

  return (
    <div className="booking-step booking-confirmation" data-testid="confirmation-step">
      <fieldset>
        <legend>Confirmación</legend>

        <div className="booking-success" role="status">
          <h2>Reserva confirmada</h2>
          <p>
            {turno.tipo_practica.nombre} el {formatFecha(turno.inicio)} a las{' '}
            {formatHora(turno.inicio)}.
          </p>
          <p>
            Sillón {turno.sillon.nombre} · Profesional {turno.odontologo.email}
          </p>
          <p>Seña: {formatPrecio(turno.monto_sena)}</p>
        </div>

        <div className="manage-token-box">
          <p>Guardá este código de gestión para consultar o cancelar tu reserva:</p>
          <code data-testid="manage-token">{manageToken}</code>
        </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={onReiniciar}>
            Hacer otra reserva
          </button>
          <a className="btn btn-primary" href={`/gestionar/${manageToken}`}>
            Gestionar mi reserva
          </a>
        </div>
      </fieldset>
    </div>
  );
}
