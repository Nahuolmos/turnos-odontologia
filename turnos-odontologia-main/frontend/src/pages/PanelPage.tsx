import './PanelPage.css';

export default function PanelPage() {
  return (
    <div className="panel-page">
      <div className="page-header">
        <h1>Panel del día</h1>
        <p className="page-subtitle">Resumen de turnos y estado de la clínica</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">12</div>
          <div className="stat-label">Turnos hoy</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">8</div>
          <div className="stat-label">Confirmados</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">3</div>
          <div className="stat-label">Pendientes</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">1</div>
          <div className="stat-label">Cancelados</div>
        </div>
      </div>

      <div className="panel-sections">
        <section className="panel-section">
          <h2>Próximos turnos</h2>
          <div className="appointment-list">
            <div className="appointment-row">
              <div className="appointment-time">09:00</div>
              <div className="appointment-patient">Juan Pérez</div>
              <div className="appointment-treatment">Limpieza</div>
              <div className="appointment-status confirmed">Confirmado</div>
              <div className="appointment-actions">
                <button className="btn btn-sm btn-secondary">Ver</button>
              </div>
            </div>
            <div className="appointment-row">
              <div className="appointment-time">10:30</div>
              <div className="appointment-patient">María González</div>
              <div className="appointment-treatment">Caries</div>
              <div className="appointment-status confirmed">Confirmado</div>
              <div className="appointment-actions">
                <button className="btn btn-sm btn-secondary">Ver</button>
              </div>
            </div>
            <div className="appointment-row">
              <div className="appointment-time">11:00</div>
              <div className="appointment-patient">Carlos López</div>
              <div className="appointment-treatment">Extracción</div>
              <div className="appointment-status pending">Pendiente</div>
              <div className="appointment-actions">
                <button className="btn btn-sm btn-secondary">Ver</button>
              </div>
            </div>
          </div>
        </section>

        <section className="panel-section">
          <h2>Odontólogos en sala</h2>
          <div className="odonto-grid">
            <div className="odonto-card">
              <div className="odonto-avatar">JP</div>
              <div className="odonto-info">
                <strong>Dr. Juan Pérez</strong>
                <span>3 turnos hoy</span>
              </div>
              <span className="odonto-status active">En sala</span>
            </div>
            <div className="odonto-card">
              <div className="odonto-avatar">MG</div>
              <div className="odonto-info">
                <strong>Dra. María González</strong>
                <span>2 turnos hoy</span>
              </div>
              <span className="odonto-status active">En sala</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}