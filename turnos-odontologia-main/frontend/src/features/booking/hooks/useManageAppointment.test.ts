import { act, renderHook, waitFor } from '@testing-library/react';
import * as bookingApi from '../api';
import type { Slot, TurnoGestion } from '../types';
import { useManageAppointment } from './useManageAppointment';

vi.mock('../api', () => ({
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
  cancelacion_retiene_sena: false,
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

describe('useManageAppointment', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('carga el turno de gestión con el token recibido', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);

    const { result } = renderHook(() => useManageAppointment('token-abc'));

    expect(result.current.cargando).toBe(true);
    await waitFor(() => {
      expect(result.current.cargando).toBe(false);
    });

    expect(mockedApi.getReservaPorToken).toHaveBeenCalledWith('token-abc');
    expect(result.current.turno?.id).toBe('turno-1');
    expect(result.current.error).toBeNull();
  });

  it('expone un error claro cuando el token no existe', async () => {
    mockedApi.getReservaPorToken.mockRejectedValue({
      isAxiosError: true,
      response: { status: 404, data: { detail: 'Turno no encontrado' } },
    });

    const { result } = renderHook(() => useManageAppointment('token-invalido'));

    await waitFor(() => {
      expect(result.current.error).toContain('Reserva no encontrada');
    });
    expect(result.current.turno).toBeNull();
    expect(result.current.cargando).toBe(false);
  });

  it('cancela y refresca el turno conservando el aviso de seña retenida', async () => {
    mockedApi.getReservaPorToken
      .mockResolvedValueOnce(turno)
      .mockResolvedValueOnce(turnoCancelado);
    mockedApi.cancelarReserva.mockResolvedValue({
      turno: turnoCancelado,
      sena_retenida: true,
    });

    const { result } = renderHook(() => useManageAppointment('token-abc'));
    await waitFor(() => {
      expect(result.current.turno).not.toBeNull();
    });

    let exito = false;
    await act(async () => {
      exito = await result.current.cancelar();
    });

    expect(exito).toBe(true);
    expect(mockedApi.cancelarReserva).toHaveBeenCalledWith('turno-1', 'token-abc');
    expect(result.current.senaRetenida).toBe(true);
    expect(result.current.turno?.estado).toBe('cancelado');
    expect(mockedApi.getReservaPorToken).toHaveBeenCalledTimes(2);
  });

  it('busca slots con la práctica del turno y la fecha elegida', async () => {
    mockedApi.getReservaPorToken.mockResolvedValue(turno);
    mockedApi.getSlots.mockResolvedValue([slot]);

    const { result } = renderHook(() => useManageAppointment('token-abc'));
    await waitFor(() => {
      expect(result.current.turno).not.toBeNull();
    });

    await act(async () => {
      await result.current.buscarSlots('2026-11-10');
    });

    expect(mockedApi.getSlots).toHaveBeenCalledWith({
      fecha: '2026-11-10',
      tipoPracticaId: 'prac-1',
    });
    expect(result.current.slots).toEqual([slot]);
    expect(result.current.error).toBeNull();
  });

  it('reprograma sin nueva seña y mantiene el token actual', async () => {
    mockedApi.getReservaPorToken
      .mockResolvedValueOnce(turno)
      .mockResolvedValueOnce(turnoReprogramado);
    mockedApi.reprogramarReserva.mockResolvedValue({
      turno: turnoReprogramado,
      sena_migrada: true,
      requiere_nueva_sena: false,
      manage_token: null,
    });

    const { result } = renderHook(() => useManageAppointment('token-abc'));
    await waitFor(() => {
      expect(result.current.turno).not.toBeNull();
    });

    let exito = false;
    await act(async () => {
      exito = await result.current.reprogramar({
        inicio: slot.inicio,
        sillon_id: slot.sillon_id,
        odontologo_id: slot.odontologo_id,
      });
    });

    expect(exito).toBe(true);
    expect(mockedApi.reprogramarReserva).toHaveBeenCalledWith('turno-1', 'token-abc', {
      inicio: slot.inicio,
      sillon_id: slot.sillon_id,
      odontologo_id: slot.odontologo_id,
    });
    expect(result.current.reprogramacion?.requiere_nueva_sena).toBe(false);
    expect(result.current.tokenActual).toBe('token-abc');
    expect(result.current.turno?.reprogramaciones_count).toBe(1);
  });

  it('adopta el manage_token nuevo cuando la reprogramación exige nueva seña', async () => {
    mockedApi.getReservaPorToken
      .mockResolvedValueOnce(turno)
      .mockResolvedValueOnce(turnoConNuevaSena);
    mockedApi.reprogramarReserva.mockResolvedValue({
      turno: turnoConNuevaSena,
      sena_migrada: false,
      requiere_nueva_sena: true,
      manage_token: 'token-nuevo',
    });

    const { result } = renderHook(() => useManageAppointment('token-abc'));
    await waitFor(() => {
      expect(result.current.turno).not.toBeNull();
    });

    await act(async () => {
      await result.current.reprogramar({ inicio: slot.inicio });
    });

    expect(result.current.tokenActual).toBe('token-nuevo');
    expect(mockedApi.getReservaPorToken).toHaveBeenLastCalledWith('token-nuevo');
    expect(result.current.turno?.estado).toBe('pendiente_sena');
    expect(result.current.reprogramacion?.manage_token).toBe('token-nuevo');
  });

  it('expone el 409 de ventana mínima y permite limpiar el error', async () => {
    mockedApi.getReservaPorToken
      .mockResolvedValueOnce(turno)
      .mockResolvedValueOnce(turno);
    mockedApi.reprogramarReserva.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: 'El nuevo horario debe tener al menos 12 horas de anticipación' },
      },
    });

    const { result } = renderHook(() => useManageAppointment('token-abc'));
    await waitFor(() => {
      expect(result.current.turno).not.toBeNull();
    });

    let exito = true;
    await act(async () => {
      exito = await result.current.reprogramar({ inicio: slot.inicio });
    });

    expect(exito).toBe(false);
    expect(result.current.error).toContain('12 horas');

    act(() => {
      result.current.limpiarError();
    });
    expect(result.current.error).toBeNull();
  });
});
