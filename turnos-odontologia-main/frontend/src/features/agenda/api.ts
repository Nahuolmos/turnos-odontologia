import { apiClient } from '@/shared/api-client';
import type {
  AgendaFiltros,
  Odontologo,
  Paciente,
  Sillon,
  TipoPractica,
  Turno,
  TurnoCancelado,
  TurnoCreatePayload,
} from './types';

const INTERNAL_BASE = '/api/internal';

function buildParams(filtros: Partial<AgendaFiltros>): Record<string, string> {
  const params: Record<string, string> = {};
  if (filtros.fecha) {
    params['fecha'] = filtros.fecha;
  }
  if (filtros.sillonId) {
    params['sillon_id'] = filtros.sillonId;
  }
  if (filtros.odontologoId) {
    params['odontologo_id'] = filtros.odontologoId;
  }
  if (filtros.estado) {
    params['estado'] = filtros.estado;
  }
  return params;
}

export async function getTurnos(filtros: Partial<AgendaFiltros> = {}): Promise<Turno[]> {
  const response = await apiClient.get<Turno[]>(`${INTERNAL_BASE}/turnos`, {
    params: buildParams(filtros),
  });
  return response.data;
}

export async function crearTurno(payload: TurnoCreatePayload): Promise<Turno> {
  const response = await apiClient.post<Turno>(`${INTERNAL_BASE}/turnos`, payload);
  return response.data;
}

export async function cancelarTurno(turnoId: string): Promise<TurnoCancelado> {
  const response = await apiClient.post<TurnoCancelado>(
    `${INTERNAL_BASE}/turnos/${turnoId}/cancelar`
  );
  return response.data;
}

export async function getPacientes(q?: string): Promise<Paciente[]> {
  const params: Record<string, string> = {};
  if (q) {
    params['q'] = q;
  }
  const response = await apiClient.get<Paciente[]>(`${INTERNAL_BASE}/pacientes`, { params });
  return response.data;
}

export async function getOdontologos(): Promise<Odontologo[]> {
  const response = await apiClient.get<Odontologo[]>(`${INTERNAL_BASE}/odontologos`);
  return response.data;
}

export async function getSillones(): Promise<Sillon[]> {
  const response = await apiClient.get<Sillon[]>(`${INTERNAL_BASE}/sillones`);
  return response.data;
}

export async function getTiposPractica(): Promise<TipoPractica[]> {
  const response = await apiClient.get<TipoPractica[]>(`${INTERNAL_BASE}/tipos-practica`);
  return response.data;
}
