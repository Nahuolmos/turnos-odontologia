import { useParams } from 'react-router-dom';
import './ManageAppointmentPage.css';

export default function ManageAppointmentPage() {
  const { token } = useParams();

  return (
    <div className="manage-page">
      <h1>Gestionar turno</h1>
      <p className="manage-intro">
        Ingresa tu código de gestión para ver, cancelar o reprogramar tu turno.
      </p>

      <div className="manage-form">
        <div className="form-group">
          <label htmlFor="token">Código de gestión</label>
          <input
            type="text"
            id="token"
            name="token"
            placeholder="Ej: ABC123XYZ"
            defaultValue={token}
            className="form-input"
            autoFocus
          />
        </div>

        <div className="form-actions">
          <button className="btn btn-primary">Buscar turno</button>
        </div>
      </div>

      <div className="manage-info">
        <h3>¿No tienes tu código?</h3>
        <p>
          El código de gestión se envía por WhatsApp y email al confirmar tu turno.
          Si no lo encuentras, contacta a la clínica.
        </p>
      </div>
    </div>
  );
}