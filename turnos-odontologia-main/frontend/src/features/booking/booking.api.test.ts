import { apiClient } from '@/shared/api-client';
import {
  cancelarReserva,
  crearReserva,
  getReserva,
  getReservaPorToken,
  getSlots,
  reprogramarReserva,
} from './api';
import { getBookingErrorMessage } from './errors';
import type {
  ReprogramacionPublica,
  ReservaCreada,
  Slot,
  TipoPractica,
  TurnoGestion,
} from './types';

vi.mock('@/shared/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

type MockFn = ReturnType<typeof vi.fn>;

const getMock = apiClient.get as unknown as MockFn;
const postMock = apiClient.post as unknown as MockFn;

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

const turnoGestion: TurnoGestion = {
  id: 'turno-1',
  inicio: slot.inicio,
  fin: slot.fin,
  estado: 'confirmado',
  monto_sena: 7500,
  reprogramaciones_count: 0,
  tipo_practica: practica,
  sillon: { id: 'sillon-1', nombre: 'Sillón 1' },
  odontologo: { id: 'odonto-1', email: 'odonto@clinica.com' },
  puede_reprogramar: true,
  puede_reprogramar_sin_sena: true,
  cancelacion_retiene_sena: false,
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

const reprogramacion: ReprogramacionPublica = {
  turno: { ...turnoGestion, reprogramaciones_count: 1 },
  sena_migrada: true,
  requiere_nueva_sena: false,
  manage_token: null,
};

describe('booking api', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('getSlots envía fecha y tipo de práctica como query params', async () => {
    getMock.mockResolvedValue({ data: [slot] });

    const resultado = await getSlots({ fecha: '2026-11-05', tipoPracticaId: 'prac-1' });

    expect(getMock).toHaveBeenCalledWith('/api/public/slots', {
      params: { fecha: '2026-11-05', tipo_practica_id: 'prac-1' },
    });
    expect(resultado).toEqual([slot]);
  });

  it('crearReserva hace POST público con los datos del paciente y el slot', async () => {
    postMock.mockResolvedValue({ data: reserva });
    const payload = {
      tipo_practica_id: 'prac-1',
      inicio: slot.inicio,
      sillon_id: 'sillon-1',
      odontologo_id: 'odonto-1',
      nombre: 'Ana Gómez',
      telefono: '+5491112345678',
    };

    const resultado = await crearReserva(payload);

    expect(postMock).toHaveBeenCalledWith('/api/public/reservas', payload);
    expect(resultado.manage_token).toBe('token-123');
  });

  it('getReserva envía el token como query param', async () => {
    getMock.mockResolvedValue({ data: reserva.turno });

    await getReserva('turno-1', 'token-123');

    expect(getMock).toHaveBeenCalledWith('/api/public/reservas/turno-1', {
      params: { token: 'token-123' },
    });
  });

  it('cancelarReserva envía el token como query param', async () => {
    postMock.mockResolvedValue({ data: { turno: reserva.turno, sena_retenida: true } });

    const resultado = await cancelarReserva('turno-1', 'token-123');

    expect(postMock).toHaveBeenCalledWith(
      '/api/public/reservas/turno-1/cancelar',
      undefined,
      { params: { token: 'token-123' } }
    );
    expect(resultado.sena_retenida).toBe(true);
  });

  it('getReservaPorToken consulta la ruta de gestión con el token codificado', async () => {
    getMock.mockResolvedValue({ data: turnoGestion });

    const resultado = await getReservaPorToken('token con espacios/1');

    expect(getMock).toHaveBeenCalledWith(
      '/api/public/reservas/gestion/token%20con%20espacios%2F1'
    );
    expect(resultado).toEqual(turnoGestion);
  });

  it('reprogramarReserva hace POST con el token como query param y el payload', async () => {
    postMock.mockResolvedValue({ data: reprogramacion });
    const payload = {
      inicio: slot.inicio,
      sillon_id: 'sillon-1',
      odontologo_id: 'odonto-1',
    };

    const resultado = await reprogramarReserva('turno-1', 'token-123', payload);

    expect(postMock).toHaveBeenCalledWith(
      '/api/public/reservas/turno-1/reprogramar',
      payload,
      { params: { token: 'token-123' } }
    );
    expect(resultado.requiere_nueva_sena).toBe(false);
    expect(resultado.manage_token).toBeNull();
  });

  it('traduce un 404 a "Reserva no encontrada"', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: { status: 404, data: { detail: 'not found' } },
    });

    expect(mensaje).toContain('Reserva no encontrada');
  });

  it('traduce un 409 a un mensaje de reintento de horario', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'slot ocupado' } },
    });

    expect(mensaje).toContain('ya fue reservado');
  });

  it('traduce el 404 de un token de gestión inválido sin perder el mensaje actual', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: { status: 404, data: { detail: 'Turno no encontrado para el token' } },
    });

    expect(mensaje).toContain('Reserva no encontrada');
    expect(mensaje).toContain('código de gestión');
  });

  it('traduce el 409 de ventana mínima con el detalle del servidor', () => {
    const detalle = 'El nuevo horario debe tener al menos 12 horas de anticipación';

    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: { status: 409, data: { detail: detalle } },
    });

    expect(mensaje).toContain('12 horas');
  });

  it('traduce el 409 de solape a un mensaje de reintento de horario', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: 'Conflicto de sillon_id entre 2026-11-05T09:00 y 2026-11-05T09:30' },
      },
    });

    expect(mensaje).toMatch(/se superpone/i);
  });

  it('traduce el 409 de solape de odontólogo en otro sillón', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          detail: 'Conflicto de odontologo_id entre 2026-11-05T09:00 y 2026-11-05T09:30',
        },
      },
    });

    expect(mensaje).toMatch(/se superpone/i);
  });

  it('traduce el 409 de un turno ya cancelado', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'Turno ya cancelado: Turno turno-1' } },
    });

    expect(mensaje).toContain('ya fue cancelado');
  });

  it('traduce el 409 de turno no reprogramable', () => {
    const mensaje = getBookingErrorMessage({
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          detail: "El turno turno-1 está en estado 'cancelado' y ya no se puede reprogramar",
        },
      },
    });

    expect(mensaje).toContain('ya no se puede reprogramar');
  });
});
