import { apiClient } from '@/shared/api-client';
import type {
  CancelacionPublica,
  ReprogramacionPublica,
  ReprogramarPayload,
  ReservaCreada,
  ReservaCreatePayload,
  Slot,
  SlotsQuery,
  TipoPractica,
  TurnoGestion,
  TurnoPublico,
} from './types';

const PUBLIC_BASE = '/api/public';

export async function getTiposPractica(): Promise<TipoPractica[]> {
  const response = await apiClient.get<TipoPractica[]>(`${PUBLIC_BASE}/tipos-practica`);
  return response.data;
}

export async function getSlots({ fecha, tipoPracticaId }: SlotsQuery): Promise<Slot[]> {
  const response = await apiClient.get<Slot[]>(`${PUBLIC_BASE}/slots`, {
    params: { fecha, tipo_practica_id: tipoPracticaId },
  });
  return response.data;
}

export async function crearReserva(payload: ReservaCreatePayload): Promise<ReservaCreada> {
  const response = await apiClient.post<ReservaCreada>(`${PUBLIC_BASE}/reservas`, payload);
  return response.data;
}

export async function getReserva(turnoId: string, token: string): Promise<TurnoPublico> {
  const response = await apiClient.get<TurnoPublico>(`${PUBLIC_BASE}/reservas/${turnoId}`, {
    params: { token },
  });
  return response.data;
}

export async function cancelarReserva(
  turnoId: string,
  token: string
): Promise<CancelacionPublica> {
  const response = await apiClient.post<CancelacionPublica>(
    `${PUBLIC_BASE}/reservas/${turnoId}/cancelar`,
    undefined,
    { params: { token } }
  );
  return response.data;
}

/** Consulta un turno solo con su `manage_token`, sin conocer el id. */
export async function getReservaPorToken(token: string): Promise<TurnoGestion> {
  const response = await apiClient.get<TurnoGestion>(
    `${PUBLIC_BASE}/reservas/gestion/${encodeURIComponent(token)}`
  );
  return response.data;
}

/** Reprograma un turno por token; el backend decide si migra o exige nueva seña. */
export async function reprogramarReserva(
  turnoId: string,
  token: string,
  payload: ReprogramarPayload
): Promise<ReprogramacionPublica> {
  const response = await apiClient.post<ReprogramacionPublica>(
    `${PUBLIC_BASE}/reservas/${turnoId}/reprogramar`,
    payload,
    { params: { token } }
  );
  return response.data;
}
