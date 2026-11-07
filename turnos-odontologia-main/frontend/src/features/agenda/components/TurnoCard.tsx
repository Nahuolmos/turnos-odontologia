import { formatHora } from '@/shared/format/date-time';
import { estadoLabel } from '../types';
import type { Turno } from '../types';

interface TurnoCardProps {
  turno: Turno;
  pacienteNombre: string;
  practicaNombre: string;
  sillonNombre: string;
  odontologoEmail: string;
  onCancelar: (turnoId: string) => void;
}

export default function TurnoCard({
  turno,
  pacienteNombre,
  practicaNombre,
  sillonNombre,
  odontologoEmail,
  onCancelar,
}: TurnoCardProps) {
  const cancelado = turno.estado === 'cancelado';

  return (
    <li className={`turno-card turno-${turno.estado}`} data-testid="turno-card">
      <div className="turno-hora">
        {formatHora(turno.inicio)} – {formatHora(turno.fin)}
      </div>
      <div className="turno-detalle">
        <strong>{pacienteNombre}</strong>
        <span>
          {practicaNombre} · {sillonNombre} · {odontologoEmail}
        </span>
      </div>
      <span className={`estado-badge estado-${turno.estado}`}>{estadoLabel(turno.estado)}</span>
      {!cancelado && (
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onCancelar(turno.id)}
          aria-label={`Cancelar turno de ${pacienteNombre}`}
        >
          Cancelar
        </button>
      )}
    </li>
  );
}
