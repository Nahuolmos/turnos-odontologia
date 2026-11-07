import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import * as agendaApi from '@/features/agenda/api';
import type { Odontologo, Paciente, Sillon, TipoPractica, Turno } from '@/features/agenda/types';
import AgendaPage from './AgendaPage';

vi.mock('@/features/agenda/api', () => ({
  getTurnos: vi.fn(),
  crearTurno: vi.fn(),
  cancelarTurno: vi.fn(),
  getPacientes: vi.fn(),
  getOdontologos: vi.fn(),
  getSillones: vi.fn(),
  getTiposPractica: vi.fn(),
}));

const mockedApi = vi.mocked(agendaApi);

const paciente: Paciente = {
  id: 'pac-1',
  clinic_id: 'clinic-1',
  nombre: 'Ana Gómez',
  telefono: '+5491112345678',
  dni: '12345678',
  is_active: true,
  created_at: '2026-11-01T00:00:00-03:00',
  updated_at: '2026-11-01T00:00:00-03:00',
};

const odontologo: Odontologo = { id: 'odonto-1', email: 'odonto@clinica.com' };

const sillon: Sillon = {
  id: 'sillon-1',
  clinic_id: 'clinic-1',
  nombre: 'Sillón 1',
  activo: true,
  is_active: true,
  created_at: '2026-11-01T00:00:00-03:00',
  updated_at: '2026-11-01T00:00:00-03:00',
};

const practica: TipoPractica = {
  id: 'prac-1',
  clinic_id: 'clinic-1',
  nombre: 'Limpieza dental',
  duracion_min: 30,
  precio_base: 25000,
  sena_pct: 30,
  activa: true,
};

const turno: Turno = {
  id: 'turno-1',
  clinic_id: 'clinic-1',
  paciente_id: 'pac-1',
  sillon_id: 'sillon-1',
  odontologo_id: 'odonto-1',
  tipo_practica_id: 'prac-1',
  inicio: '2026-11-05T10:00:00-03:00',
  fin: '2026-11-05T10:30:00-03:00',
  estado: 'confirmado',
  reprogramaciones_count: 0,
  monto_sena: 7500,
  is_active: true,
  created_at: null,
  updated_at: null,
};

function configurarMocks(): void {
  mockedApi.getTurnos.mockResolvedValue([turno]);
  mockedApi.getPacientes.mockResolvedValue([paciente]);
  mockedApi.getOdontologos.mockResolvedValue([odontologo]);
  mockedApi.getSillones.mockResolvedValue([sillon]);
  mockedApi.getTiposPractica.mockResolvedValue([practica]);
  mockedApi.crearTurno.mockResolvedValue(turno);
  mockedApi.cancelarTurno.mockResolvedValue({
    turno: { ...turno, estado: 'cancelado' },
    sena_retenida: false,
  });
}

describe('AgendaPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    configurarMocks();
  });

  it('carga los turnos al montar y muestra paciente y práctica', async () => {
    render(<AgendaPage />);

    expect(await screen.findByText('Ana Gómez')).toBeInTheDocument();
    expect(screen.getByText(/Limpieza dental · Sillón 1/)).toBeInTheDocument();
    expect(mockedApi.getTurnos).toHaveBeenCalledWith(
      expect.objectContaining({ fecha: expect.any(String) })
    );
  });

  it('aplica el filtro de estado y vuelve a consultar la agenda', async () => {
    render(<AgendaPage />);
    await screen.findByText('Ana Gómez');

    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'cancelado' } });

    await waitFor(() => {
      expect(mockedApi.getTurnos).toHaveBeenLastCalledWith(
        expect.objectContaining({ estado: 'cancelado' })
      );
    });
  });

  it('muestra el estado vacío cuando no hay turnos', async () => {
    mockedApi.getTurnos.mockResolvedValue([]);

    render(<AgendaPage />);

    expect(await screen.findByTestId('agenda-empty')).toBeInTheDocument();
  });

  it('muestra un error de red con opción de reintentar', async () => {
    mockedApi.getTurnos.mockRejectedValue(new Error('La API no responde'));

    render(<AgendaPage />);

    const alerta = await screen.findByTestId('agenda-error');
    expect(alerta).toHaveTextContent('La API no responde');
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });

  it('abre el formulario de alta con los catálogos cargados', async () => {
    render(<AgendaPage />);
    await screen.findByText('Ana Gómez');

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo turno' }));

    expect(screen.getByLabelText('Paciente')).toBeInTheDocument();
    expect(screen.getByLabelText('Práctica')).toBeInTheDocument();
    expect(screen.getByLabelText('Sillón')).toBeInTheDocument();
    expect(screen.getByLabelText('Profesional')).toBeInTheDocument();
  });

  it('crea un turno con el payload esperado', async () => {
    render(<AgendaPage />);
    await screen.findByText('Ana Gómez');

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo turno' }));
    fireEvent.change(screen.getByLabelText('Paciente'), { target: { value: 'pac-1' } });
    fireEvent.change(screen.getByLabelText('Práctica'), { target: { value: 'prac-1' } });
    fireEvent.change(screen.getByLabelText('Sillón'), { target: { value: 'sillon-1' } });
    fireEvent.change(screen.getByLabelText('Profesional'), { target: { value: 'odonto-1' } });
    fireEvent.change(screen.getByLabelText('Inicio'), {
      target: { value: '2026-11-05T10:00' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Crear turno' }));

    await waitFor(() => {
      expect(mockedApi.crearTurno).toHaveBeenCalledWith({
        paciente_id: 'pac-1',
        tipo_practica_id: 'prac-1',
        sillon_id: 'sillon-1',
        odontologo_id: 'odonto-1',
        inicio: '2026-11-05T13:00:00.000Z',
      });
    });
  });

  it('cancela un turno y recarga la agenda', async () => {
    render(<AgendaPage />);
    await screen.findByText('Ana Gómez');

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar turno de Ana Gómez' }));

    await waitFor(() => {
      expect(mockedApi.cancelarTurno).toHaveBeenCalledWith('turno-1');
    });
    expect(await screen.findByText(/Turno cancelado/)).toBeInTheDocument();
  });
});
