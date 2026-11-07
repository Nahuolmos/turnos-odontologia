const CLINIC_TIME_ZONE = 'America/Argentina/Buenos_Aires';
const BUENOS_AIRES_OFFSET = '-03:00';

function timeZonePart(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  const part = parts.find((candidate) => candidate.type === type);
  return part?.value ?? '';
}

/** Fecha de hoy (YYYY-MM-DD) en la zona horaria de la clínica. */
export function todayIso(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: CLINIC_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  return `${timeZonePart(parts, 'year')}-${timeZonePart(parts, 'month')}-${timeZonePart(parts, 'day')}`;
}

/** Hora local de la clínica a partir de un ISO devuelto por la API. */
export function formatHora(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat('es-AR', {
    timeZone: CLINIC_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

/** Fecha legible en la zona horaria de la clínica. */
export function formatFecha(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat('es-AR', {
    timeZone: CLINIC_TIME_ZONE,
    dateStyle: 'long',
  }).format(date);
}

/**
 * Convierte un valor de `<input type="datetime-local">` al ISO con offset que
 * espera la API. La clínica opera en UTC-3 durante todo el año.
 */
export function toApiDateTime(localValue: string): string {
  if (localValue === '') {
    return '';
  }
  if (/(?:Z|[+-]\d{2}:\d{2})$/.test(localValue)) {
    return new Date(localValue).toISOString();
  }
  const withSeconds = localValue.length === 16 ? `${localValue}:00` : localValue;
  return new Date(`${withSeconds}${BUENOS_AIRES_OFFSET}`).toISOString();
}

/** Importe en pesos argentinos sin decimales. */
export function formatPrecio(valor: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0,
  }).format(valor);
}
