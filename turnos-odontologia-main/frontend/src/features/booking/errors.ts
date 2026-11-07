import axios from 'axios';
import { getApiErrorMessage } from '@/shared/api-client/error';

interface ProblemDetail {
  detail?: unknown;
}

const MENSAJE_HORARIO_OCUPADO = 'El horario elegido ya fue reservado. Elegí otro horario.';
const MENSAJE_SOLAPE = 'Ese horario se superpone con otro turno. Elegí otro horario.';

function detalleString(error: unknown): string {
  if (!axios.isAxiosError<ProblemDetail>(error)) {
    return '';
  }
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : '';
}

/**
 * Mensajes de error del flujo público de reservas y de la gestión por token.
 *
 * Para 409 prioriza el detalle del servidor cuando distingue una regla de
 * negocio propia de la gestión (ventana de 12 h, turno terminal, cancelación
 * repetida) y conserva el mensaje de reintento de horario para el resto.
 */
export function getBookingErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 404) {
      return 'Reserva no encontrada. Verificá el código de gestión.';
    }
    if (error.response?.status === 409) {
      const detalle = detalleString(error);
      const detalleNormalizado = detalle.toLowerCase();
      if (detalleNormalizado.includes('12 horas')) {
        return detalle;
      }
      if (detalleNormalizado.includes('no se puede reprogramar')) {
        return detalle;
      }
      if (detalleNormalizado.includes('ya cancelado')) {
        return 'Este turno ya fue cancelado. No se puede volver a cancelar.';
      }
      if (
        detalleNormalizado.includes('conflicto') ||
        detalleNormalizado.includes('solapa')
      ) {
        return MENSAJE_SOLAPE;
      }
      return MENSAJE_HORARIO_OCUPADO;
    }
    if (error.response?.status === 422) {
      return 'Revisá los datos ingresados: el teléfono o el horario no son válidos.';
    }
  }
  return getApiErrorMessage(error);
}
