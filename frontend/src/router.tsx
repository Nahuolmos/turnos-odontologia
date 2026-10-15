import { createBrowserRouter, Navigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/hooks/useAuth';
import Layout from '@/layouts/Layout';
import PublicLayout from '@/layouts/PublicLayout';
import HomePage from '@/pages/HomePage';
import BookingPage from '@/pages/BookingPage';
import ManageAppointmentPage from '@/pages/ManageAppointmentPage';
import LoginPage from '@/pages/LoginPage';
import AgendaPage from '@/pages/AgendaPage';
import PanelPage from '@/pages/PanelPage';
import AdminPage from '@/pages/AdminPage';

interface ProtectedRouteProps {
  allowedRoles?: string[];
  children: React.ReactNode;
}

function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: window.location.pathname }} />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

interface PublicRouteProps {
  children: React.ReactNode;
}

function PublicRoute({ children }: PublicRouteProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <PublicLayout>
        <PublicRoute>
          <HomePage />
        </PublicRoute>
      </PublicLayout>
    ),
  },
  {
    path: '/reservar',
    element: (
      <PublicLayout>
        <PublicRoute>
          <BookingPage />
        </PublicRoute>
      </PublicLayout>
    ),
  },
  {
    path: '/gestionar/:token',
    element: (
      <PublicLayout>
        <ManageAppointmentPage />
      </PublicLayout>
    ),
  },
  {
    path: '/login',
    element: (
      <PublicLayout>
        <PublicRoute>
          <LoginPage />
        </PublicRoute>
      </PublicLayout>
    ),
  },
  {
    path: '/agenda',
    element: (
      <Layout>
        <ProtectedRoute allowedRoles={['odonto', 'admin']}>
          <AgendaPage />
        </ProtectedRoute>
      </Layout>
    ),
  },
  {
    path: '/panel',
    element: (
      <Layout>
        <ProtectedRoute allowedRoles={['recepcion', 'admin']}>
          <PanelPage />
        </ProtectedRoute>
      </Layout>
    ),
  },
  {
    path: '/admin',
    element: (
      <Layout>
        <ProtectedRoute allowedRoles={['admin']}>
          <AdminPage />
        </ProtectedRoute>
      </Layout>
    ),
  },
]);