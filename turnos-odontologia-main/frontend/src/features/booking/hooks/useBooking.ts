import { useCallback, useEffect, useState } from 'react';
import { todayIso } from '@/shared/format/date-time';
import { crearReserva, getSlots, getTiposPractica } from '../api';
import { getBookingErrorMessage } from '../errors';
import type { ReservaCreada, Slot, TipoPractica } from '../types';

export interface UseBookingResult {
  practicas: TipoPractica[];
  practicaId: string;
  fecha: string;
  slots: Slot[];
  slotElegido: Slot | null;
  reserva: ReservaCreada | null;
  cargandoPracticas: boolean;
  cargandoSlots: boolean;
  enviando: boolean;
  error: string | null;
  setPracticaId: (id: string) => void;
  setFecha: (fecha: string) => void;
  recargarPracticas: () => Promise<void>;
  buscarSlots: () => Promise<void>;
  reservar: (nombre: string, telefono: string) => Promise<boolean>;
  seleccionarSlot: (slot: Slot) => void;
  reiniciar: () => void;
  limpiarError: () => void;
}

export function useBooking(): UseBookingResult {
  const [practicas, setPracticas] = useState<TipoPractica[]>([]);
  const [practicaId, setPracticaId] = useState('');
  const [fecha, setFecha] = useState(todayIso());
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotElegido, setSlotElegido] = useState<Slot | null>(null);
  const [reserva, setReserva] = useState<ReservaCreada | null>(null);
  const [cargandoPracticas, setCargandoPracticas] = useState(true);
  const [cargandoSlots, setCargandoSlots] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recargarPracticas = useCallback(async () => {
    setCargandoPracticas(true);
    setError(null);
    try {
      const data = await getTiposPractica();
      setPracticas(data);
    } catch (caught) {
      setError(getBookingErrorMessage(caught));
    } finally {
      setCargandoPracticas(false);
    }
  }, []);

  useEffect(() => {
    void recargarPracticas();
  }, [recargarPracticas]);

  const buscarSlots = useCallback(async () => {
    if (practicaId === '') {
      setError('Elegí una práctica antes de buscar horarios.');
      return;
    }
    setCargandoSlots(true);
    setError(null);
    setSlots([]);
    setSlotElegido(null);
    try {
      const data = await getSlots({ fecha, tipoPracticaId: practicaId });
      setSlots(data);
      if (data.length === 0) {
        setError('No hay horarios disponibles para esa fecha. Probá con otro día.');
      }
    } catch (caught) {
      setError(getBookingErrorMessage(caught));
    } finally {
      setCargandoSlots(false);
    }
  }, [fecha, practicaId]);

  const seleccionarSlot = useCallback((slot: Slot) => {
    setSlotElegido(slot);
    setError(null);
  }, []);

  const reservar = useCallback(
    async (nombre: string, telefono: string): Promise<boolean> => {
      if (!slotElegido || practicaId === '') {
        setError('Faltan datos para confirmar la reserva.');
        return false;
      }
      setEnviando(true);
      setError(null);
      try {
        const creada = await crearReserva({
          tipo_practica_id: practicaId,
          inicio: slotElegido.inicio,
          sillon_id: slotElegido.sillon_id,
          odontologo_id: slotElegido.odontologo_id,
          nombre,
          telefono,
        });
        setReserva(creada);
        return true;
      } catch (caught) {
        setError(getBookingErrorMessage(caught));
        return false;
      } finally {
        setEnviando(false);
      }
    },
    [practicaId, slotElegido]
  );

  const reiniciar = useCallback(() => {
    setReserva(null);
    setSlotElegido(null);
    setSlots([]);
    setError(null);
    setPracticaId('');
    setFecha(todayIso());
  }, []);

  const limpiarError = useCallback(() => {
    setError(null);
  }, []);

  return {
    practicas,
    practicaId,
    fecha,
    slots,
    slotElegido,
    reserva,
    cargandoPracticas,
    cargandoSlots,
    enviando,
    error,
    setPracticaId,
    setFecha,
    recargarPracticas,
    buscarSlots,
    reservar,
    seleccionarSlot,
    reiniciar,
    limpiarError,
  };
}
