import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import * as bookingApi from '@/features/booking/api';
import type { ReservaCreada, Slot, TipoPractica } from '@/features/booking/types';
import BookingPage from './BookingPage';

vi.mock('@/features/booking/api', () => ({
  getTiposPractica: vi.fn(),
  getSlots: vi.fn(),
  crearReserva: vi.fn(),
  getReserva: vi.fn(),
  cancelarReserva: vi.fn(),
}));

const mockedApi = vi.mocked(bookingApi);

const practica: TipoPractica = {
  id: 'prac-1',
  clinic_id: 'clinic-1',
  nombre: 'Limpieza dental',
  duracion_min: 30,
  precio_base: 25000,
  sena_pct: 30,
  activa: true,
};

const slot: Slot = {
  inicio: '2026-11-05T09:00:00-03:00',
  fin: '2026-11-05T09:30:00-03:00',
  sillon_id: 'sillon-1',
  odontologo_id: 'odonto-1',
};

const reserva: ReservaCreada = {
  turno: {
    id: 'turno-1',
    inicio: slot.inicio,
    fin: slot.fin,
    estado: 'pendiente_sena',
    monto_sena: 7500,
    reprogramaciones_count: 0,
    tipo_practica: practica,
    sillon: { id: 'sillon-1', nombre: 'Sillón 1' },
    odontologo: { id: 'odonto-1', email: 'odonto@clinica.com' },
  },
  manage_token: 'token-123',
};

function configurarMocks(): void {
  mockedApi.getTiposPractica.mockResolvedValue([practica]);
  mockedApi.getSlots.mockResolvedValue([slot]);
  mockedApi.crearReserva.mockResolvedValue(reserva);
}

async function irAPasoDatos(): Promise<void> {
  render(<BookingPage />);
  fireEvent.click(await screen.findByRole('radio', { name: /Limpieza dental/i }));
  fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
  fireEvent.click(screen.getByRole('button', { name: 'Buscar horarios' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Elegir horario 09:00' }));
}

function completarDatos(nombre: string, telefono: string): void {
  fireEvent.change(screen.getByLabelText('Nombre y apellido'), { target: { value: nombre } });
  fireEvent.change(screen.getByLabelText('Teléfono'), { target: { value: telefono } });
}

describe('BookingPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    configurarMocks();
  });

  it('carga las prácticas públicas al montar', async () => {
    render(<BookingPage />);

    expect(await screen.findByRole('radio', { name: /Limpieza dental/i })).toBeInTheDocument();
    expect(mockedApi.getTiposPractica).toHaveBeenCalledTimes(1);
  });

  it('completa el flujo: práctica, fecha, slot, datos y confirmación con token', async () => {
    await irAPasoDatos();

    expect(mockedApi.getSlots).toHaveBeenCalledWith(
      expect.objectContaining({ tipoPracticaId: 'prac-1' })
    );

    completarDatos('Ana Gómez', '+5491112345678');
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reserva' }));

    expect(await screen.findByText('Reserva confirmada')).toBeInTheDocument();
    expect(mockedApi.crearReserva).toHaveBeenCalledWith({
      tipo_practica_id: 'prac-1',
      inicio: slot.inicio,
      sillon_id: 'sillon-1',
      odontologo_id: 'odonto-1',
      nombre: 'Ana Gómez',
      telefono: '+5491112345678',
    });

    expect(screen.getByTestId('manage-token')).toHaveTextContent('token-123');
    expect(screen.getByRole('link', { name: 'Gestionar mi reserva' })).toHaveAttribute(
      'href',
      '/gestionar/token-123'
    );
  });

  it('muestra el conflicto 409 y permite volver a elegir horario', async () => {
    mockedApi.crearReserva.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'slot tomado' } },
    });

    await irAPasoDatos();
    completarDatos('Ana Gómez', '+5491112345678');
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reserva' }));

    expect(await screen.findByText(/ya fue reservado/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Volver a elegir horario' }));

    await waitFor(() => {
      expect(mockedApi.getSlots).toHaveBeenCalledTimes(2);
    });
  });

  it('valida el teléfono antes de llamar a la API', async () => {
    await irAPasoDatos();
    completarDatos('Ana Gómez', '123');
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reserva' }));

    expect(await screen.findByText(/teléfono válido/i)).toBeInTheDocument();
    expect(mockedApi.crearReserva).not.toHaveBeenCalled();
  });

  it('muestra un mensaje cuando no hay horarios disponibles', async () => {
    mockedApi.getSlots.mockResolvedValue([]);

    render(<BookingPage />);
    fireEvent.click(await screen.findByRole('radio', { name: /Limpieza dental/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
    fireEvent.click(screen.getByRole('button', { name: 'Buscar horarios' }));

    expect(await screen.findByText(/No hay horarios disponibles/i)).toBeInTheDocument();
  });
});
