import axios from 'axios';

interface ProblemDetail {
  detail?: unknown;
  title?: unknown;
}

const FALLBACK_MESSAGE = 'Ocurrió un error inesperado. Intentá nuevamente.';

/**
 * Extrae un mensaje legible de una respuesta de error de la API.
 *
 * El backend responde errores con el formato `application/problem+json`
 * (`{ type, title, status, detail }`), por lo que priorizamos `detail`.
 */
export function getApiErrorMessage(
  error: unknown,
  fallback: string = FALLBACK_MESSAGE
): string {
  if (axios.isAxiosError<ProblemDetail>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim() !== '') {
      return detail;
    }
    const title = error.response?.data?.title;
    if (
      typeof title === 'string' &&
      title.trim() !== '' &&
      title !== 'HTTP Error' &&
      title !== 'Not Found'
    ) {
      return title;
    }
    switch (error.response?.status) {
      case 401:
        return 'Tu sesión expiró. Iniciá sesión nuevamente.';
      case 403:
        return 'No tenés permisos para realizar esta acción.';
      case 404:
        return 'No se encontró el recurso solicitado.';
      case 409:
        return 'La operación entra en conflicto con otro turno.';
      case 422:
        return 'Los datos enviados no son válidos.';
      default:
        return fallback;
    }
  }
  if (error instanceof Error && error.message.trim() !== '') {
    return error.message;
  }
  return fallback;
}
