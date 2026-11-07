import { useMemo, useState, type FormEvent } from 'react';
import AgendaFilters from '@/features/agenda/components/AgendaFilters';
import TurnoCard from '@/features/agenda/components/TurnoCard';
import { useAgenda } from '@/features/agenda/hooks/useAgenda';
import { ESTADOS_TURNO } from '@/features/agenda/types';
import type { TurnoCreatePayload } from '@/features/agenda/types';
import { toApiDateTime } from '@/shared/format/date-time';
import './AgendaPage.css';

interface FormularioTurno {
  pacienteId: string;
  tipoPracticaId: string;
  sillonId: string;
  odontologoId: string;
  inicio: string;
}

const FORMULARIO_VACIO: FormularioTurno = {
  pacienteId: '',
  tipoPracticaId: '',
  sillonId: '',
  odontologoId: '',
  inicio: '',
};

function claseLeyenda(estado: string): string {
  switch (estado) {
    case 'confirmado':
      return 'confirmed';
    case 'reprogramado':
      return 'pending';
    case 'realizado':
      return 'completed';
    case 'cancelado':
      return 'cancelled';
    default:
      return 'pending';
  }
}

export default function AgendaPage() {
  const agenda = useAgenda();
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [formulario, setFormulario] = useState<FormularioTurno>(FORMULARIO_VACIO);
  const [errorFormulario, setErrorFormulario] = useState<string | null>(null);

  const pacientesPorId = useMemo(
    () => new Map(agenda.pacientes.map((paciente) => [paciente.id, paciente.nombre])),
    [agenda.pacientes]
  );
  const odontologosPorId = useMemo(
    () => new Map(agenda.odontologos.map((odontologo) => [odontologo.id, odontologo.email])),
    [agenda.odontologos]
  );
  const sillonesPorId = useMemo(
    () => new Map(agenda.sillones.map((sillon) => [sillon.id, sillon.nombre])),
    [agenda.sillones]
  );
  const practicasPorId = useMemo(
    () =>
      new Map(agenda.tiposPractica.map((practica) => [practica.id, practica.nombre])),
    [agenda.tiposPractica]
  );

  const actualizarFormulario = (campo: keyof FormularioTurno, valor: string) => {
    setFormulario((previo) => ({ ...previo, [campo]: valor }));
  };

  const abrirFormulario = () => {
    agenda.limpiarMensajes();
    setErrorFormulario(null);
    setMostrarFormulario(true);
  };

  const crearTurno = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorFormulario(null);
    if (
      formulario.pacienteId === '' ||
      formulario.tipoPracticaId === '' ||
      formulario.sillonId === '' ||
      formulario.odontologoId === '' ||
      formulario.inicio === ''
    ) {
      setErrorFormulario('Completá paciente, práctica, sillón, profesional e inicio.');
      return;
    }

    const payload: TurnoCreatePayload = {
      paciente_id: formulario.pacienteId,
      tipo_practica_id: formulario.tipoPracticaId,
      sillon_id: formulario.sillonId,
      odontologo_id: formulario.odontologoId,
      inicio: toApiDateTime(formulario.inicio),
    };

    const creado = await agenda.crear(payload);
    if (creado) {
      setFormulario(FORMULARIO_VACIO);
      setMostrarFormulario(false);
    }
  };

  return (
    <div className="agenda-page">
      <div className="page-header">
        <div>
          <h1>Agenda</h1>
          <p className="page-subtitle">Turnos de la clínica con filtros por fecha, sillón y estado</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={abrirFormulario}>
          Nuevo turno
        </button>
      </div>

      <AgendaFilters
        filtros={agenda.filtros}
        sillones={agenda.sillones}
        odontologos={agenda.odontologos}
        onChange={agenda.setFiltro}
      />

      {agenda.accionOk && (
        <p className="agenda-success" role="status">
          {agenda.accionOk}
        </p>
      )}
      {agenda.accionError && !mostrarFormulario && (
        <p className="agenda-alert" role="alert">
          {agenda.accionError}
        </p>
      )}

      {mostrarFormulario && (
        <form className="agenda-form" onSubmit={(event) => void crearTurno(event)}>
          <h2>Nuevo turno</h2>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="form-paciente">Paciente</label>
              <select
                id="form-paciente"
                className="form-select"
                value={formulario.pacienteId}
                onChange={(event) => actualizarFormulario('pacienteId', event.target.value)}
              >
                <option value="">Seleccioná un paciente</option>
                {agenda.pacientes.map((paciente) => (
                  <option key={paciente.id} value={paciente.id}>
                    {paciente.nombre} · {paciente.telefono}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="form-practica">Práctica</label>
              <select
                id="form-practica"
                className="form-select"
                value={formulario.tipoPracticaId}
                onChange={(event) => actualizarFormulario('tipoPracticaId', event.target.value)}
              >
                <option value="">Seleccioná una práctica</option>
                {agenda.tiposPractica.map((practica) => (
                  <option key={practica.id} value={practica.id}>
                    {practica.nombre} ({practica.duracion_min} min)
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="form-sillon">Sillón</label>
              <select
                id="form-sillon"
                className="form-select"
                value={formulario.sillonId}
                onChange={(event) => actualizarFormulario('sillonId', event.target.value)}
              >
                <option value="">Seleccioná un sillón</option>
                {agenda.sillones.map((sillon) => (
                  <option key={sillon.id} value={sillon.id}>
                    {sillon.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="form-odontologo">Profesional</label>
              <select
                id="form-odontologo"
                className="form-select"
                value={formulario.odontologoId}
                onChange={(event) => actualizarFormulario('odontologoId', event.target.value)}
              >
                <option value="">Seleccioná un profesional</option>
                {agenda.odontologos.map((odontologo) => (
                  <option key={odontologo.id} value={odontologo.id}>
                    {odontologo.email}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="form-inicio">Inicio</label>
              <input
                type="datetime-local"
                id="form-inicio"
                className="form-input"
                value={formulario.inicio}
                onChange={(event) => actualizarFormulario('inicio', event.target.value)}
              />
            </div>
          </div>

          {(errorFormulario ?? agenda.accionError) && (
            <p className="agenda-alert" role="alert">
              {errorFormulario ?? agenda.accionError}
            </p>
          )}

          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setMostrarFormulario(false)}
            >
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary">
              Crear turno
            </button>
          </div>
        </form>
      )}

      {agenda.loading ? (
        <p className="agenda-status" data-testid="agenda-loading">
          Cargando agenda…
        </p>
      ) : agenda.error ? (
        <div className="agenda-alert" role="alert" data-testid="agenda-error">
          <p>{agenda.error}</p>
          <button type="button" className="btn btn-secondary" onClick={() => void agenda.recargar()}>
            Reintentar
          </button>
        </div>
      ) : agenda.turnos.length === 0 ? (
        <p className="agenda-status" data-testid="agenda-empty">
          No hay turnos para los filtros seleccionados.
        </p>
      ) : (
        <ul className="turno-list" data-testid="turno-list">
          {agenda.turnos.map((turno) => (
            <TurnoCard
              key={turno.id}
              turno={turno}
              pacienteNombre={pacientesPorId.get(turno.paciente_id) ?? 'Paciente sin nombre'}
              practicaNombre={practicasPorId.get(turno.tipo_practica_id) ?? 'Práctica'}
              sillonNombre={sillonesPorId.get(turno.sillon_id) ?? 'Sillón'}
              odontologoEmail={odontologosPorId.get(turno.odontologo_id) ?? 'Profesional'}
              onCancelar={(turnoId) => void agenda.cancelar(turnoId)}
            />
          ))}
        </ul>
      )}

      <div className="legend">
        {ESTADOS_TURNO.map((estado) => (
          <div key={estado.value} className="legend-item">
            <span className={`legend-color ${claseLeyenda(estado.value)}`}></span> {estado.label}
          </div>
        ))}
      </div>
    </div>
  );
}
