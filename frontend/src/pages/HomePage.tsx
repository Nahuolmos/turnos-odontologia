import { Link } from 'react-router-dom';
import './HomePage.css';

export default function HomePage() {
  return (
    <div className="home-page">
      <section className="hero">
        <h1>Bienvenido a Turnos Odontología</h1>
        <p className="hero-subtitle">
          Reserva tu turno 24/7 sin necesidad de registrarte
        </p>
        <Link to="/reservar" className="btn btn-primary btn-large">
          Reservar turno
        </Link>
      </section>

      <section className="features">
        <h2>¿Cómo funciona?</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>1. Elige tu tratamiento</h3>
            <p>Selecciona la práctica odontológica que necesitas</p>
          </div>
          <div className="feature-card">
            <h3>2. Busca disponibilidad</h3>
            <p>Consulta los horarios disponibles en tiempo real</p>
          </div>
          <div className="feature-card">
            <h3>3. Confirma con seña</h3>
            <p>Paga la seña con Mercado Pago para confirmar</p>
          </div>
          <div className="feature-card">
            <h3>4. Recibe recordatorio</h3>
            <p>Te avisamos por WhatsApp 24hs antes</p>
          </div>
        </div>
      </section>

      <section className="cta">
        <p>¿Ya tienes un turno?</p>
        <Link to="/gestionar" className="btn btn-secondary">
          Gestionar mi turno
        </Link>
      </section>
    </div>
  );
}