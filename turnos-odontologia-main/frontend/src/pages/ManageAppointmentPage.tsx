import { useState } from 'react';
import { useParams } from 'react-router-dom';
import ConfirmCancelModal from '@/features/booking/components/ConfirmCancelModal';
import ManageSummary from '@/features/booking/components/ManageSummary';
import ReprogramForm from '@/features/booking/components/ReprogramForm';
import { useManageAppointment } from '@/features/booking/hooks/useManageAppointment';
import { estadoTurnoLabel } from '@/features/booking/labels';
import type { Slot } from '@/features/booking/types';
import { formatPrecio } from '@/shared/format/date-time';
import './ManageAppointmentPage.css';

const ESTADOS_TERMINALES: ReadonlySet<string> = new Set([
  'cancelado',
  'completado',
  'ausente',
]);

export default function ManageAppointmentPage() {
  const { token } = useParams<{ token: string }>();
  const manage = useManageAppointment(token ?? '');
  const [modalAbierto, setModalAbierto] = useState(false);
  const [eligiendoHorario, setEligiendoHorario] = useState(false);

  const confirmarCancelacion = async (): Promise<void> => {
    await manage.cancelar();
    setModalAbierto(false);
  };

  const confirmarReprogramacion = async (slot: Slot): Promise<void> => {
    const exito = await manage.reprogramar({
      inicio: slot.inicio,
      sillon_id: slot.sillon_id,
      odontologo_id: slot.odontologo_id,
    });
    if (exito) {
      setEligiendoHorario(false);
    }
  };

  const turno = manage.turno;

  if (manage.cargando && !turno) {
    return (
      <div className="manage-page">
        <h1>Gestionar turno</h1>
        <p className="manage-status" role="status">
          Cargando tu turno…
        </p>
      </div>
    );
  }

  if (!turno) {
    return (
      <div className="manage-page">
        <h1>Gestionar turno</h1>
        <div className="manage-alert" role="alert">
          {manage.error ?? 'No pudimos cargar tu turno. Intentá nuevamente.'}
        </div>
        <button type="button" className="btn btn-primary" onClick={() => void manage.recargar()}>
          Reintentar
        </button>

        <div className="manage-info">
          <h2>¿No encontrás tu código?</h2>
          <p>
            El código de gestión se envía por WhatsApp y email al confirmar tu turno. Si no lo
            encontrás, contactá a la clínica.
          </p>
        </div>
      </div>
    );
  }

  const terminal = ESTADOS_TERMINALES.has(turno.estado);
  const nuevaSena = manage.reprogramacion;
  const requiereNuevaSena = nuevaSena?.requiere_nueva_sena === true;

  return (
    <div className="manage-page">
      <h1>Gestionar turno</h1>
      <p className="manage-intro">
        Revisá los datos de tu turno y, si está vigente, podés cancelarlo o reprogramarlo.
      </p>

      <ManageSummary turno={turno} />

      {manage.senaRetenida === true && (
        <div className="manage-alert manage-alert--warning" role="status">
          Turno cancelado. Como faltaban menos de 12 horas, la seña abonada quedó retenida.
        </div>
      )}

      {manage.senaRetenida === false && (
        <div className="manage-alert manage-alert--success" role="status">
          Turno cancelado sin retención de seña. El horario ya está disponible.
        </div>
      )}

      {terminal && (
        <p className="manage-terminal" role="status">
          Este turno está {estadoTurnoLabel(turno.estado).toLowerCase()} y no admite más acciones.
        </p>
      )}

      {manage.error && (
        <div className="manage-alert" role="alert">
          {manage.error}
        </div>
      )}

      {requiereNuevaSena && nuevaSena && (
        <section className="manage-card manage-new-sena" data-testid="nueva-sena">
          <h2>Necesitás abonar una nueva seña</h2>
          <p>
            La reprogramación generó un turno nuevo: el anterior quedó cancelado con la seña
            retenida.
          </p>
          <p>
            Monto de la nueva seña: <strong>{formatPrecio(turno.monto_sena)}</strong>
          </p>
          <p>
            Estado del turno nuevo: <strong>{estadoTurnoLabel(turno.estado)}</strong>
          </p>
          {nuevaSena.manage_token !== null && (
            <div className="manage-token-box">
              <p>Guardá este nuevo código de gestión para las próximas acciones:</p>
              <code data-testid="nuevo-manage-token">{nuevaSena.manage_token}</code>
            </div>
          )}
          {nuevaSena.manage_token !== null && (
            <a className="btn btn-primary" href={`/gestionar/${nuevaSena.manage_token}`}>
              Gestionar el turno nuevo
            </a>
          )}
        </section>
      )}

      {!terminal && turno.puede_reprogramar && !requiereNuevaSena && !eligiendoHorario && (
        <div className="manage-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setEligiendoHorario(true)}
          >
            Reprogramar turno
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setModalAbierto(true)}
          >
            Cancelar turno
          </button>
        </div>
      )}

      {!terminal && turno.puede_reprogramar && eligiendoHorario && (
        <ReprogramForm
          turno={turno}
          slots={manage.slots}
          cargandoSlots={manage.cargandoSlots}
          reprogramando={manage.reprogramando}
          onBuscar={(fecha) => {
            void manage.buscarSlots(fecha);
          }}
          onReprogramar={(slot) => {
            void confirmarReprogramacion(slot);
          }}
          onVolver={() => {
            manage.limpiarError();
            setEligiendoHorario(false);
          }}
        />
      )}

      {modalAbierto && (
        <ConfirmCancelModal
          retieneSena={turno.cancelacion_retiene_sena}
          cancelando={manage.cancelando}
          onVolver={() => setModalAbierto(false)}
          onConfirmar={() => {
            void confirmarCancelacion();
          }}
        />
      )}
    </div>
  );
}
