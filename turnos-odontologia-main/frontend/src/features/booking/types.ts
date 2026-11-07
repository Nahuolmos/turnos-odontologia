import type { TipoPractica } from '@/features/agenda/types';

export type { TipoPractica };

export interface Slot {
  inicio: string;
  fin: string;
  sillon_id: string;
  odontologo_id: string;
}

export interface SillonResumen {
  id: string;
  nombre: string;
}

export interface OdontologoResumen {
  id: string;
  email: string;
}

export interface TurnoPublico {
  id: string;
  inicio: string;
  fin: string;
  estado: string;
  monto_sena: number;
  reprogramaciones_count: number;
  tipo_practica: TipoPractica;
  sillon: SillonResumen;
  odontologo: OdontologoResumen;
}

/** Turno público enriquecido con los indicadores de autogestión del servidor. */
export interface TurnoGestion extends TurnoPublico {
  puede_reprogramar: boolean;
  puede_reprogramar_sin_sena: boolean;
  cancelacion_retiene_sena: boolean;
}

export interface ReservaCreatePayload {
  tipo_practica_id: string;
  inicio: string;
  sillon_id: string;
  odontologo_id: string;
  nombre: string;
  telefono: string;
}

export interface ReservaCreada {
  turno: TurnoPublico;
  manage_token: string;
}

export interface CancelacionPublica {
  turno: TurnoGestion;
  sena_retenida: boolean;
}

export interface ReprogramarPayload {
  inicio: string;
  sillon_id?: string;
  odontologo_id?: string;
}

export interface ReprogramacionPublica {
  turno: TurnoGestion;
  sena_migrada: boolean;
  requiere_nueva_sena: boolean;
  manage_token: string | null;
}

export interface SlotsQuery {
  fecha: string;
  tipoPracticaId: string;
}
