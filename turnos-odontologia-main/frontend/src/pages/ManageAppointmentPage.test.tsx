import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as bookingApi from '@/features/booking/api';
import type { Slot, TurnoGestion } from '@/features/booking/types';
import ManageAppointmentPage from './ManageAppointmentPage';

vi.mock('@/features/booking/api', () => ({
  getReservaPorToken: vi.fn(),
  cancelarReserva: vi.fn(),
  reprogramarReserva: vi.fn(),
  getSlots: vi.fn(),
}));

const mockedApi = vi.mocked(bookingApi);

const slot: Slot = {
  inicio: '2026-11-10T09:00:00-03:00',
  fin: '2026-11-10T09:30:00-03:00',
  sillon_id: 'sillon-1',
  odontologo_id: 'odonto-1',
};

const turno: TurnoGestion = {
  id: 'turno-1',
  inicio: '2026-11-12T10:00:00-03:00',
  fin: '2026-11-12T10:30:00-03:00',
  estado: 'confirmado',
  monto_sena: 7500,
  reprogramaciones_count: 0,
  tipo_practica: {
    id: 'prac-1',
    clinic_id: 'clinic-1',
    nombre: 'Limpieza dental',
    duracion_min: 30,
    precio_base: 25000,
    sena_pct: 30,
    activa: true,
  },
  sillon: { id: 'sillon-1', nombre: 'Sillón 1' },
  odontologo: { id: 'odonto-1', email: 'odonto@clinica.com' },
  puede_reprogramar: true,
  puede_reprogramar_sin_sena: true,
  cancelacion_retiene_sena: false,
};

const turnoCancelado: TurnoGestion = {
  ...turno,
  estado: 'cancelado',
  puede_reprogramar: false,
  puede_reprogramar_sin_sena: false,
};

const turnoReprogramado: TurnoGestion = {
  ...turno,
  inicio: slot.inicio,
  fin: slot.fin,
  reprogramaciones_count: 1,
  puede_reprogramar_sin_sena: false,
};

const turnoConNuevaSena: TurnoGestion = {
  ...turnoReprogramado,
  id: 'turno-2',
  estado: 'pendiente_sena',
  reprogramaciones_count: 2,
};

function renderPage(token: string): void {
  render(
    <MemoryRouter initialEntries={[`/gestionar/${token}`]}>
      <Routes>
        <Route path="/gestionar/:token" element={<ManageAppointmentPage />} />
      </Routes>
    </MemoryRouter>
  );
}

async function abrirModalDeCancelacion(): Promise<HTMLElement> {
  fireEvent.click(await screen.findByRole('button', { name: 'Cancelar turno' }));
  return screen.getByRole('dialog');
}

describe('ManageAppointmentPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('carga el turno y muestra fecha, práctica, sillón, profesional, estado, seña y reprogramaciones', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);

    renderPage('token-abc');

    expect(await screen.findByRole('heading', { name: 'Gestionar turno' })).toBeInTheDocument();
    expect(mockedApi.getReservaPorToken).toHaveBeenCalledWith('token-abc');

    expect(screen.getByText('Limpieza dental')).toBeInTheDocument();
    expect(screen.getByText('12 de noviembre de 2026')).toBeInTheDocument();
    expect(screen.getByText('10:00')).toBeInTheDocument();
    expect(screen.getByText('Sillón 1')).toBeInTheDocument();
    expect(screen.getByText('odonto@clinica.com')).toBeInTheDocument();
    expect(screen.getByText('Confirmado')).toBeInTheDocument();
    expect(screen.getByText(/7\.500/)).toBeInTheDocument();
    expect(screen.getByTestId('reprogramaciones')).toHaveTextContent('0');
  });

  it('muestra un error claro cuando el token es inválido y permite reintentar', async () => {
    mockedApi.getReservaPorToken.mockRejectedValue({
      isAxiosError: true,
      response: { status: 404, data: { detail: 'Turno no encontrado' } },
    });

    renderPage('token-invalido');

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('Reserva no encontrada');
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });

  it('muestra el turno cancelado sin acciones de gestión', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turnoCancelado);

    renderPage('token-abc');

    expect(await screen.findByTestId('estado-turno')).toHaveTextContent('Cancelado');
    expect(screen.queryByRole('button', { name: 'Cancelar turno' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reprogramar turno' })).not.toBeInTheDocument();
    expect(screen.getByText(/no admite más acciones/i)).toBeInTheDocument();
  });

  it('trata igual los estados completado y ausente', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue({
      ...turno,
      estado: 'ausente',
      puede_reprogramar: false,
      puede_reprogramar_sin_sena: false,
    });

    renderPage('token-abc');

    expect(await screen.findByTestId('estado-turno')).toHaveTextContent('Ausente');
    expect(screen.queryByRole('button', { name: 'Cancelar turno' })).not.toBeInTheDocument();
    expect(screen.getByText(/no admite más acciones/i)).toBeInTheDocument();
  });

  it('abre el modal, advierte la retención de seña y confirma la cancelación', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue({
      ...turno,
      cancelacion_retiene_sena: true,
    });
    mockedApi.cancelarReserva.mockResolvedValue({
      turno: turnoCancelado,
      sena_retenida: true,
    });

    renderPage('token-abc');
    const dialogo = await abrirModalDeCancelacion();

    expect(dialogo).toHaveAttribute('aria-modal', 'true');
    expect(dialogo).toHaveTextContent(/seña.*retenida/i);
    expect(screen.getByRole('button', { name: 'Volver' })).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar cancelación' }));

    await waitFor(() => {
      expect(mockedApi.cancelarReserva).toHaveBeenCalledWith('turno-1', 'token-abc');
    });
  });

  it('no advierte retención cuando la cancelación está en término', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);

    renderPage('token-abc');
    const dialogo = await abrirModalDeCancelacion();

    expect(dialogo).not.toHaveTextContent(/seña.*retenida/i);
    expect(dialogo).toHaveTextContent(/liberar el horario/i);
  });

  it('cierra el modal con "Volver" sin llamar a la API', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);

    renderPage('token-abc');
    await abrirModalDeCancelacion();

    fireEvent.click(screen.getByRole('button', { name: 'Volver' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(mockedApi.cancelarReserva).not.toHaveBeenCalled();
  });

  it('cierra el modal con Escape sin llamar a la API', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);

    renderPage('token-abc');
    await abrirModalDeCancelacion();

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(mockedApi.cancelarReserva).not.toHaveBeenCalled();
  });

  it('advierte que hace falta una nueva seña al reprogramar un turno ya reprogramado', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turnoReprogramado);

    renderPage('token-abc');
    fireEvent.click(await screen.findByRole('button', { name: 'Reprogramar turno' }));

    expect(screen.getByTestId('reprogram-form')).toHaveTextContent(/nueva seña/i);
  });

  it('busca slots con la práctica del turno, elige uno y confirma la reprogramación', async () => {
    mockedApi.getReservaPorToken
      .mockResolvedValueOnce(turno)
      .mockResolvedValueOnce(turnoReprogramado);
    mockedApi.getSlots.mockResolvedValue([slot]);
    mockedApi.reprogramarReserva.mockResolvedValue({
      turno: turnoReprogramado,
      sena_migrada: true,
      requiere_nueva_sena: false,
      manage_token: null,
    });

    renderPage('token-abc');
    fireEvent.click(await screen.findByRole('button', { name: 'Reprogramar turno' }));

    fireEvent.change(screen.getByLabelText('Nueva fecha'), { target: { value: '2026-11-10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar horarios' }));

    await waitFor(() => {
      expect(mockedApi.getSlots).toHaveBeenCalledWith({
        fecha: '2026-11-10',
        tipoPracticaId: 'prac-1',
      });
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Elegir horario 09:00' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reprogramación' }));

    await waitFor(() => {
      expect(mockedApi.reprogramarReserva).toHaveBeenCalledWith('turno-1', 'token-abc', {
        inicio: slot.inicio,
        sillon_id: slot.sillon_id,
        odontologo_id: slot.odontologo_id,
      });
    });
  });

  it('muestra el bloque de nueva seña con monto, estado y el token nuevo', async () => {
    mockedApi.getReservaPorToken
      .mockResolvedValueOnce(turno)
      .mockResolvedValueOnce(turnoConNuevaSena);
    mockedApi.getSlots.mockResolvedValue([slot]);
    mockedApi.reprogramarReserva.mockResolvedValue({
      turno: turnoConNuevaSena,
      sena_migrada: false,
      requiere_nueva_sena: true,
      manage_token: 'token-nuevo',
    });

    renderPage('token-abc');
    fireEvent.click(await screen.findByRole('button', { name: 'Reprogramar turno' }));
    fireEvent.change(screen.getByLabelText('Nueva fecha'), { target: { value: '2026-11-10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar horarios' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Elegir horario 09:00' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reprogramación' }));

    const bloque = await screen.findByTestId('nueva-sena');
    expect(bloque).toHaveTextContent(/nueva seña/i);
    expect(bloque).toHaveTextContent(/7\.500/);
    expect(bloque).toHaveTextContent('Pendiente de seña');
    expect(bloque).toHaveTextContent('token-nuevo');
  });

  it('muestra el 409 del servidor y permite reintentar la reprogramación', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);
    mockedApi.getSlots.mockResolvedValue([slot]);
    mockedApi.reprogramarReserva.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: 'El nuevo horario debe tener al menos 12 horas de anticipación' },
      },
    });

    renderPage('token-abc');
    fireEvent.click(await screen.findByRole('button', { name: 'Reprogramar turno' }));
    fireEvent.change(screen.getByLabelText('Nueva fecha'), { target: { value: '2026-11-10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar horarios' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Elegir horario 09:00' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reprogramación' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('12 horas');

    fireEvent.change(screen.getByLabelText('Nueva fecha'), { target: { value: '2026-11-11' } });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar horarios' }));

    await waitFor(() => {
      expect(mockedApi.getSlots).toHaveBeenLastCalledWith({
        fecha: '2026-11-11',
        tipoPracticaId: 'prac-1',
      });
    });
    expect(mockedApi.getSlots).toHaveBeenCalledTimes(2);
  });
});
