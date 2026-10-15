import { Link } from 'react-router-dom';
import './PublicLayout.css';

interface PublicLayoutProps {
  children: React.ReactNode;
}

export default function PublicLayout({ children }: PublicLayoutProps) {
  return (
    <div className="public-layout" data-testid="app-root">
      <header className="public-layout-header">
        <nav className="public-layout-nav">
          <Link to="/" className="public-layout-brand">
            Turnos Odontología
          </Link>
          <ul className="public-layout-menu">
            <li>
              <Link to="/reservar">Reservar turno</Link>
            </li>
            <li>
              <Link to="/login">Iniciar sesión</Link>
            </li>
          </ul>
        </nav>
      </header>
      <main className="public-layout-main">
        {children}
      </main>
    </div>
  );
}