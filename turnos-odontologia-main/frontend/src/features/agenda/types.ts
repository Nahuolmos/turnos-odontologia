export const ESTADOS_TURNO = [
  { value: 'pendiente_sena', label: 'Pendiente de seña' },
  { value: 'confirmado', label: 'Confirmado' },
  { value: 'reprogramado', label: 'Reprogramado' },
  { value: 'realizado', label: 'Realizado' },
  { value: 'cancelado', label: 'Cancelado' },
] as const;

export type EstadoTurno = (typeof ESTADOS_TURNO)[number]['value'];

export interface TipoPractica {
  id: string;
  clinic_id: string;
  nombre: string;
  duracion_min: number;
  precio_base: number;
  sena_pct: number;
  activa: boolean;
}

export interface Turno {
  id: string;
  clinic_id: string;
  paciente_id: string;
  sillon_id: string;
  odontologo_id: string;
  tipo_practica_id: string;
  inicio: string;
  fin: string;
  estado: string;
  reprogramaciones_count: number;
  monto_sena: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface Paciente {
  id: string;
  clinic_id: string;
  nombre: string;
  telefono: string;
  dni: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Odontologo {
  id: string;
  email: string;
}

export interface Sillon {
  id: string;
  clinic_id: string;
  nombre: string;
  activo: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TurnoCreatePayload {
  paciente_id: string;
  sillon_id: string;
  odontologo_id: string;
  tipo_practica_id: string;
  inicio: string;
}

export interface TurnoCancelado {
  turno: Turno;
  sena_retenida: boolean;
}

export interface AgendaFiltros {
  fecha: string;
  sillonId: string;
  odontologoId: string;
  estado: string;
}

export function estadoLabel(estado: string): string {
  const encontrado = ESTADOS_TURNO.find((candidate) => candidate.value === estado);
  return encontrado?.label ?? estado;
}
