import './AgendaPage.css';

export default function AgendaPage() {
  return (
    <div className="agenda-page">
      <div className="page-header">
        <h1>Agenda</h1>
        <p className="page-subtitle">Vista de turnos del día</p>
      </div>

      <div className="agenda-controls">
        <div className="date-picker">
          <label htmlFor="date" className="visually-hidden">Fecha</label>
          <input type="date" id="date" className="form-input" defaultValue={new Date().toISOString().split('T')[0]} />
        </div>
        <div className="filter-group">
          <label htmlFor="odontologo" className="visually-hidden">Odontólogo</label>
          <select id="odontologo" className="form-select">
            <option value="">Todos los odontólogos</option>
            <option value="1">Dr. Juan Pérez</option>
            <option value="2">Dra. María González</option>
          </select>
        </div>
      </div>

      <div className="agenda-grid">
        <div className="time-column">
          <div className="time-slot-header">Hora</div>
          {[...Array(12)].map((_, i) => (
            <div key={i} className="time-slot">
              {String(8 + i).padStart(2, '0')}:00
            </div>
          ))}
        </div>
        <div className="appointments-column">
          <div className="appointment-header">Turnos</div>
          {[...Array(12)].map((_, i) => (
            <div key={i} className="appointment-slot">
              {i === 2 && (
                <div className="appointment-card">
                  <strong>Juan Pérez</strong> - Limpieza
                </div>
              )}
              {i === 5 && (
                <div className="appointment-card confirmed">
                  <strong>María González</strong> - Caries
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="legend">
        <div className="legend-item">
          <span className="legend-color pending"></span> Pendiente
        </div>
        <div className="legend-item">
          <span className="legend-color confirmed"></span> Confirmado
        </div>
        <div className="legend-item">
          <span className="legend-color completed"></span> Realizado
        </div>
        <div className="legend-item">
          <span className="legend-color cancelled"></span> Cancelado
        </div>
      </div>
    </div>
  );
}