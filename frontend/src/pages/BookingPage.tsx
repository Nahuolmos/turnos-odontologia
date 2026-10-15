import './BookingPage.css';

export default function BookingPage() {
  return (
    <div className="booking-page">
      <h1>Reservar turno</h1>
      <p className="booking-intro">
        Selecciona el tratamiento y busca disponibilidad para reservar tu turno.
      </p>

      <div className="booking-steps">
        <div className="step active">
          <span className="step-number">1</span>
          <span className="step-label">Tratamiento</span>
        </div>
        <div className="step">
          <span className="step-number">2</span>
          <span className="step-label">Horario</span>
        </div>
        <div className="step">
          <span className="step-number">3</span>
          <span className="step-label">Datos</span>
        </div>
        <div className="step">
          <span className="step-number">4</span>
          <span className="step-label">Pago</span>
        </div>
      </div>

      <div className="booking-form">
        <fieldset>
          <legend>Tratamiento</legend>
          <div className="treatment-options">
            <label className="treatment-option">
              <input type="radio" name="treatment" value="limpieza" />
              <span className="treatment-info">
                <strong>Limpieza dental</strong>
                <small>30 min - $15.000</small>
              </span>
            </label>
            <label className="treatment-option">
              <input type="radio" name="treatment" value="caries" />
              <span className="treatment-info">
                <strong>Tratamiento de caries</strong>
                <small>45 min - $25.000</small>
              </span>
            </label>
            <label className="treatment-option">
              <input type="radio" name="treatment" value="extraccion" />
              <span className="treatment-info">
                <strong>Extracción simple</strong>
                <small>30 min - $20.000</small>
              </span>
            </label>
            <label className="treatment-option">
              <input type="radio" name="treatment" value="ortodoncia" />
              <span className="treatment-info">
                <strong>Control ortodoncia</strong>
                <small>20 min - $12.000</small>
              </span>
            </label>
          </div>
        </fieldset>

        <div className="form-actions">
          <button className="btn btn-primary" disabled>Continuar</button>
        </div>
      </div>
    </div>
  );
}