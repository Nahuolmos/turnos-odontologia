const ETIQUETAS_ESTADO: Readonly<Record<string, string>> = {
  pendiente_sena: 'Pendiente de seña',
  confirmado: 'Confirmado',
  reprogramado: 'Reprogramado',
  realizado: 'Realizado',
  completado: 'Completado',
  cancelado: 'Cancelado',
  ausente: 'Ausente',
};

/** Etiqueta legible del estado del turno, con fallback al valor crudo. */
export function estadoTurnoLabel(estado: string): string {
  return ETIQUETAS_ESTADO[estado] ?? estado;
}
