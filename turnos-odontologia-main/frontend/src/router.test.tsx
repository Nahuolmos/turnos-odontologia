import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import { appRoutes } from '@/router';

const authState = vi.hoisted(() => ({
  user: null as { id: string; email: string; role: string; nombre: string } | null,
}));

vi.mock('@/features/auth/hooks/useAuth', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: authState.user,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
  }),
}));

vi.mock('@/pages/BookingPage', () => ({
  default: () => <div>booking-page-stub</div>,
}));

vi.mock('@/pages/AgendaPage', () => ({
  default: () => <div>agenda-page-stub</div>,
}));

vi.mock('@/pages/ManageAppointmentPage', async () => {
  const { useParams } = await import('react-router-dom');
  function GestionarPageStub() {
    const { token } = useParams<{ token: string }>();
    return <div>gestionar-page-stub:{token ?? ''}</div>;
  }
  return { default: GestionarPageStub };
});

function renderRuta(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

describe('router', () => {
  it('/reservar renderiza BookingPage sin login', () => {
    authState.user = null;

    renderRuta('/reservar');

    expect(screen.getByText('booking-page-stub')).toBeInTheDocument();
  });

  it('/gestionar/:token pasa el token a la página de gestión', () => {
    authState.user = null;

    renderRuta('/gestionar/abc-token');

    expect(screen.getByText('gestionar-page-stub:abc-token')).toBeInTheDocument();
  });

  it('/agenda es accesible para un odontólogo autenticado', () => {
    authState.user = {
      id: 'user-1',
      email: 'odonto@clinica.com',
      role: 'odonto',
      nombre: 'Dra. Odonto',
    };

    renderRuta('/agenda');

    expect(screen.getByText('agenda-page-stub')).toBeInTheDocument();
  });

  it('/agenda redirige a inicio para un rol sin permiso', () => {
    authState.user = {
      id: 'user-2',
      email: 'recepcion@clinica.com',
      role: 'recepcion',
      nombre: 'Recepción',
    };

    renderRuta('/agenda');

    expect(screen.queryByText('agenda-page-stub')).not.toBeInTheDocument();
  });
});
