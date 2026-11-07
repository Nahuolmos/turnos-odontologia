import { useCallback, useEffect, useState } from 'react';
import { getApiErrorMessage } from '@/shared/api-client/error';
import { todayIso } from '@/shared/format/date-time';
import {
  cancelarTurno,
  crearTurno,
  getOdontologos,
  getPacientes,
  getSillones,
  getTiposPractica,
  getTurnos,
} from '../api';
import type {
  AgendaFiltros,
  Odontologo,
  Paciente,
  Sillon,
  TipoPractica,
  Turno,
  TurnoCreatePayload,
} from '../types';

export interface UseAgendaResult {
  turnos: Turno[];
  pacientes: Paciente[];
  odontologos: Odontologo[];
  sillones: Sillon[];
  tiposPractica: TipoPractica[];
  filtros: AgendaFiltros;
  loading: boolean;
  error: string | null;
  accionError: string | null;
  accionOk: string | null;
  setFiltro: <K extends keyof AgendaFiltros>(key: K, value: AgendaFiltros[K]) => void;
  recargar: () => Promise<void>;
  crear: (payload: TurnoCreatePayload) => Promise<boolean>;
  cancelar: (turnoId: string) => Promise<boolean>;
  limpiarMensajes: () => void;
}

const filtrosIniciales: AgendaFiltros = {
  fecha: todayIso(),
  sillonId: '',
  odontologoId: '',
  estado: '',
};

export function useAgenda(): UseAgendaResult {
  const [filtros, setFiltros] = useState<AgendaFiltros>(filtrosIniciales);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [pacientes, setPacientes] = useState<Paciente[]>([]);
  const [odontologos, setOdontologos] = useState<Odontologo[]>([]);
  const [sillones, setSillones] = useState<Sillon[]>([]);
  const [tiposPractica, setTiposPractica] = useState<TipoPractica[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accionError, setAccionError] = useState<string | null>(null);
  const [accionOk, setAccionOk] = useState<string | null>(null);

  const recargar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTurnos(filtros);
      setTurnos(data);
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  useEffect(() => {
    let cancelado = false;
    const cargarCatalogos = async () => {
      try {
        const [pacientesData, odontologosData, sillonesData, practicasData] = await Promise.all([
          getPacientes(),
          getOdontologos(),
          getSillones(),
          getTiposPractica(),
        ]);
        if (!cancelado) {
          setPacientes(pacientesData);
          setOdontologos(odontologosData);
          setSillones(sillonesData);
          setTiposPractica(practicasData);
        }
      } catch (caught) {
        if (!cancelado) {
          setError(getApiErrorMessage(caught));
        }
      }
    };
    void cargarCatalogos();
    return () => {
      cancelado = true;
    };
  }, []);

  const setFiltro = useCallback(
    <K extends keyof AgendaFiltros>(key: K, value: AgendaFiltros[K]) => {
      setFiltros((previos) => ({ ...previos, [key]: value }));
    },
    []
  );

  const limpiarMensajes = useCallback(() => {
    setAccionError(null);
    setAccionOk(null);
  }, []);

  const crear = useCallback(
    async (payload: TurnoCreatePayload): Promise<boolean> => {
      setAccionError(null);
      setAccionOk(null);
      try {
        await crearTurno(payload);
        setAccionOk('Turno creado correctamente.');
        await recargar();
        return true;
      } catch (caught) {
        setAccionError(getApiErrorMessage(caught));
        return false;
      }
    },
    [recargar]
  );

  const cancelar = useCallback(
    async (turnoId: string): Promise<boolean> => {
      setAccionError(null);
      setAccionOk(null);
      try {
        const resultado = await cancelarTurno(turnoId);
        setAccionOk(
          resultado.sena_retenida
            ? 'Turno cancelado. La seña quedó retenida por cancelación tardía.'
            : 'Turno cancelado. La seña será devuelta.'
        );
        await recargar();
        return true;
      } catch (caught) {
        setAccionError(getApiErrorMessage(caught));
        return false;
      }
    },
    [recargar]
  );

  return {
    turnos,
    pacientes,
    odontologos,
    sillones,
    tiposPractica,
    filtros,
    loading,
    error,
    accionError,
    accionOk,
    setFiltro,
    recargar,
    crear,
    cancelar,
    limpiarMensajes,
  };
}
