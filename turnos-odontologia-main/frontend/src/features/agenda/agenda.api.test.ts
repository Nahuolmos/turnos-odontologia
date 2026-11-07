import { apiClient } from '@/shared/api-client';
import { getApiErrorMessage } from '@/shared/api-client/error';
import { cancelarTurno, crearTurno, getPacientes, getTurnos } from './api';
import type { Turno } from './types';

vi.mock('@/shared/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

type MockFn = ReturnType<typeof vi.fn>;

const getMock = apiClient.get as unknown as MockFn;
const postMock = apiClient.post as unknown as MockFn;

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

describe('agenda api', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('getTurnos arma query params solo con filtros activos', async () => {
    getMock.mockResolvedValue({ data: [turno] });

    const resultado = await getTurnos({
      fecha: '2026-11-05',
      sillonId: 'sillon-1',
      odontologoId: '',
      estado: 'confirmado',
    });

    expect(getMock).toHaveBeenCalledWith('/api/internal/turnos', {
      params: {
        fecha: '2026-11-05',
        sillon_id: 'sillon-1',
        estado: 'confirmado',
      },
    });
    expect(resultado).toEqual([turno]);
  });

  it('crearTurno hace POST al endpoint interno con el payload', async () => {
    postMock.mockResolvedValue({ data: turno });
    const payload = {
      paciente_id: 'pac-1',
      sillon_id: 'sillon-1',
      odontologo_id: 'odonto-1',
      tipo_practica_id: 'prac-1',
      inicio: '2026-11-05T13:00:00.000Z',
    };

    await crearTurno(payload);

    expect(postMock).toHaveBeenCalledWith('/api/internal/turnos', payload);
  });

  it('cancelarTurno hace POST al endpoint de cancelación', async () => {
    postMock.mockResolvedValue({ data: { turno, sena_retenida: false } });

    const resultado = await cancelarTurno('turno-1');

    expect(postMock).toHaveBeenCalledWith('/api/internal/turnos/turno-1/cancelar');
    expect(resultado.sena_retenida).toBe(false);
  });

  it('getPacientes incluye el filtro q cuando se envía', async () => {
    getMock.mockResolvedValue({ data: [] });

    await getPacientes('Ana');

    expect(getMock).toHaveBeenCalledWith('/api/internal/pacientes', {
      params: { q: 'Ana' },
    });
  });

  it('traduce el detalle de un 409 a un mensaje legible', () => {
    const mensaje = getApiErrorMessage({
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: 'Solape de sillón en el rango solicitado' },
      },
    });

    expect(mensaje).toBe('Solape de sillón en el rango solicitado');
  });

  it('usa un mensaje de respaldo para errores desconocidos', () => {
    expect(getApiErrorMessage({})).toContain('error inesperado');
  });
});
