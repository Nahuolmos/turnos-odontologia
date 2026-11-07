import { useCallback, useEffect, useState } from 'react';
import {
  cancelarReserva,
  getReservaPorToken,
  getSlots,
  reprogramarReserva,
} from '../api';
import { getBookingErrorMessage } from '../errors';
import type {
  ReprogramacionPublica,
  ReprogramarPayload,
  Slot,
  TurnoGestion,
} from '../types';

export interface UseManageAppointmentResult {
  turno: TurnoGestion | null;
  cargando: boolean;
  cancelando: boolean;
  reprogramando: boolean;
  cargandoSlots: boolean;
  slots: Slot[];
  error: string | null;
  senaRetenida: boolean | null;
  reprogramacion: ReprogramacionPublica | null;
  /** Token vigente: adopta el nuevo `manage_token` tras una segunda reprogramación. */
  tokenActual: string;
  recargar: () => Promise<void>;
  cancelar: () => Promise<boolean>;
  buscarSlots: (fecha: string) => Promise<void>;
  reprogramar: (payload: ReprogramarPayload) => Promise<boolean>;
  limpiarError: () => void;
}

export function useManageAppointment(token: string): UseManageAppointmentResult {
  const [turno, setTurno] = useState<TurnoGestion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [cancelando, setCancelando] = useState(false);
  const [reprogramando, setReprogramando] = useState(false);
  const [cargandoSlots, setCargandoSlots] = useState(false);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [senaRetenida, setSenaRetenida] = useState<boolean | null>(null);
  const [reprogramacion, setReprogramacion] = useState<ReprogramacionPublica | null>(null);

  const tokenActual = reprogramacion?.manage_token ?? token;

  const recargar = useCallback(async (): Promise<void> => {
    setCargando(true);
    setError(null);
    try {
      const data = await getReservaPorToken(token);
      setTurno(data);
      setReprogramacion(null);
      setSenaRetenida(null);
    } catch (caught) {
      setTurno(null);
      setError(getBookingErrorMessage(caught));
    } finally {
      setCargando(false);
    }
  }, [token]);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  const cancelar = useCallback(async (): Promise<boolean> => {
    if (!turno) {
      setError('No hay un turno cargado para cancelar.');
      return false;
    }
    setCancelando(true);
    setError(null);
    try {
      const resultado = await cancelarReserva(turno.id, tokenActual);
      setSenaRetenida(resultado.sena_retenida);
      setTurno(resultado.turno);
      try {
        setTurno(await getReservaPorToken(tokenActual));
      } catch {
        // La respuesta de la cancelación ya trae el turno actualizado.
      }
      return true;
    } catch (caught) {
      setError(getBookingErrorMessage(caught));
      return false;
    } finally {
      setCancelando(false);
    }
  }, [turno, tokenActual]);

  const buscarSlots = useCallback(
    async (fecha: string): Promise<void> => {
      if (!turno) {
        setError('No hay un turno cargado para reprogramar.');
        return;
      }
      setCargandoSlots(true);
      setError(null);
      setSlots([]);
      try {
        const data = await getSlots({ fecha, tipoPracticaId: turno.tipo_practica.id });
        setSlots(data);
        if (data.length === 0) {
          setError('No hay horarios disponibles para esa fecha. Probá con otro día.');
        }
      } catch (caught) {
        setError(getBookingErrorMessage(caught));
      } finally {
        setCargandoSlots(false);
      }
    },
    [turno]
  );

  const reprogramar = useCallback(
    async (payload: ReprogramarPayload): Promise<boolean> => {
      if (!turno) {
        setError('No hay un turno cargado para reprogramar.');
        return false;
      }
      setReprogramando(true);
      setError(null);
      try {
        const resultado = await reprogramarReserva(turno.id, tokenActual, payload);
        setReprogramacion(resultado);
        setTurno(resultado.turno);
        setSlots([]);
        const tokenSiguiente = resultado.manage_token ?? tokenActual;
        try {
          setTurno(await getReservaPorToken(tokenSiguiente));
        } catch {
          // La respuesta de la reprogramación ya trae el turno actualizado.
        }
        return true;
      } catch (caught) {
        setError(getBookingErrorMessage(caught));
        return false;
      } finally {
        setReprogramando(false);
      }
    },
    [turno, tokenActual]
  );

  const limpiarError = useCallback(() => {
    setError(null);
  }, []);

  return {
    turno,
    cargando,
    cancelando,
    reprogramando,
    cargandoSlots,
    slots,
    error,
    senaRetenida,
    reprogramacion,
    tokenActual,
    recargar,
    cancelar,
    buscarSlots,
    reprogramar,
    limpiarError,
  };
}
