import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router-dom';
import { AuthProvider } from '@/features/auth/hooks/useAuth';
import { router } from '@/router';
import '@testing-library/jest-dom';

vi.mock('@/shared/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}));

function renderApp() {
  return render(
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}

describe('App', () => {
  it('renders without crashing', () => {
    renderApp();
    const root = screen.getByTestId('app-root');
    expect(root).toBeInTheDocument();
  });

  it('router mounts correctly', () => {
    renderApp();
    expect(screen.getByText('Turnos Odontología')).toBeInTheDocument();
  });
});