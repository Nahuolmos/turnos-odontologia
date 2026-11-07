import { formatFecha, formatHora, formatPrecio } from '@/shared/format/date-time';
import { estadoTurnoLabel } from '../labels';
import type { TurnoGestion } from '../types';

interface ManageSummaryProps {
  turno: TurnoGestion;
}

const ESTADOS_TERMINALES: ReadonlySet<string> = new Set([
  'cancelado',
  'completado',
  'ausente',
]);

export default function ManageSummary({ turno }: ManageSummaryProps) {
  const terminal = ESTADOS_TERMINALES.has(turno.estado);

  return (
    <section className="manage-card" aria-labelledby="manage-summary-title">
      <h2 id="manage-summary-title">Tu turno</h2>
      <dl className="manage-summary">
        <div className="manage-summary-item">
          <dt>Práctica</dt>
          <dd>{turno.tipo_practica.nombre}</dd>
        </div>
        <div className="manage-summary-item">
          <dt>Fecha</dt>
          <dd>{formatFecha(turno.inicio)}</dd>
        </div>
        <div className="manage-summary-item">
          <dt>Hora</dt>
          <dd>{formatHora(turno.inicio)}</dd>
        </div>
        <div className="manage-summary-item">
          <dt>Sillón</dt>
          <dd>{turno.sillon.nombre}</dd>
        </div>
        <div className="manage-summary-item">
          <dt>Profesional</dt>
          <dd>{turno.odontologo.email}</dd>
        </div>
        <div className="manage-summary-item">
          <dt>Estado</dt>
          <dd>
            <span
              className={`manage-badge ${terminal ? 'manage-badge--terminal' : 'manage-badge--vigente'}`}
              data-testid="estado-turno"
            >
              {estadoTurnoLabel(turno.estado)}
            </span>
          </dd>
        </div>
        <div className="manage-summary-item">
          <dt>Seña</dt>
          <dd>{formatPrecio(turno.monto_sena)}</dd>
        </div>
        <div className="manage-summary-item">
          <dt>Reprogramaciones</dt>
          <dd data-testid="reprogramaciones">{turno.reprogramaciones_count}</dd>
        </div>
      </dl>
    </section>
  );
}
