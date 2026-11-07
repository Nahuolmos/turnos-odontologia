import { ESTADOS_TURNO } from '../types';
import type { AgendaFiltros, Odontologo, Sillon } from '../types';

interface AgendaFiltersProps {
  filtros: AgendaFiltros;
  sillones: Sillon[];
  odontologos: Odontologo[];
  onChange: <K extends keyof AgendaFiltros>(key: K, value: AgendaFiltros[K]) => void;
}

export default function AgendaFilters({
  filtros,
  sillones,
  odontologos,
  onChange,
}: AgendaFiltersProps) {
  return (
    <div className="agenda-controls" data-testid="agenda-filters">
      <div className="date-picker">
        <label htmlFor="fecha">Fecha</label>
        <input
          type="date"
          id="fecha"
          className="form-input"
          value={filtros.fecha}
          onChange={(event) => onChange('fecha', event.target.value)}
        />
      </div>

      <div className="filter-group">
        <label htmlFor="sillon">Filtrar por sillón</label>
        <select
          id="sillon"
          className="form-select"
          value={filtros.sillonId}
          onChange={(event) => onChange('sillonId', event.target.value)}
        >
          <option value="">Todos los sillones</option>
          {sillones.map((sillon) => (
            <option key={sillon.id} value={sillon.id}>
              {sillon.nombre}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="odontologo">Filtrar por profesional</label>
        <select
          id="odontologo"
          className="form-select"
          value={filtros.odontologoId}
          onChange={(event) => onChange('odontologoId', event.target.value)}
        >
          <option value="">Todos los profesionales</option>
          {odontologos.map((odontologo) => (
            <option key={odontologo.id} value={odontologo.id}>
              {odontologo.email}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="estado">Estado</label>
        <select
          id="estado"
          className="form-select"
          value={filtros.estado}
          onChange={(event) => onChange('estado', event.target.value)}
        >
          <option value="">Todos los estados</option>
          {ESTADOS_TURNO.map((estado) => (
            <option key={estado.value} value={estado.value}>
              {estado.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
