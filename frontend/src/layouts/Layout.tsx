import { Link, useLocation } from 'react-router-dom';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const navigation = [
    { path: '/agenda', label: 'Agenda', roles: ['odonto', 'admin'] },
    { path: '/panel', label: 'Panel', roles: ['recepcion', 'admin'] },
    { path: '/admin', label: 'Admin', roles: ['admin'] },
  ];

  return (
    <div className="layout" data-testid="app-root">
      <header className="layout-header">
        <nav className="layout-nav">
          <Link to="/" className="layout-brand">
            Turnos Odontología
          </Link>
          <ul className="layout-menu">
            {navigation.map((item) => (
              <li key={item.path}>
                <Link to={item.path} className={location.pathname === item.path ? 'active' : ''}>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main className="layout-main">
        {children}
      </main>
    </div>
  );
}