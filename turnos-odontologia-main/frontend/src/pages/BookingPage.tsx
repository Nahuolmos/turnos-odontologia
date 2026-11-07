import { useState } from 'react';
import ConfirmationStep from '@/features/booking/components/ConfirmationStep';
import PatientStep from '@/features/booking/components/PatientStep';
import PracticeStep from '@/features/booking/components/PracticeStep';
import SlotStep from '@/features/booking/components/SlotStep';
import { useBooking } from '@/features/booking/hooks/useBooking';
import type { Slot } from '@/features/booking/types';
import './BookingPage.css';

type Paso = 'practica' | 'horario' | 'datos' | 'confirmacion';

const PASOS: ReadonlyArray<{ id: Paso; label: string }> = [
  { id: 'practica', label: 'Tratamiento' },
  { id: 'horario', label: 'Horario' },
  { id: 'datos', label: 'Datos' },
  { id: 'confirmacion', label: 'Confirmación' },
];

export default function BookingPage() {
  const booking = useBooking();
  const [paso, setPaso] = useState<Paso>('practica');

  const practicaSeleccionada = booking.practicas.find(
    (practica) => practica.id === booking.practicaId
  );
  const pasoActual = PASOS.findIndex((candidate) => candidate.id === paso);

  const elegirSlot = (slot: Slot) => {
    booking.seleccionarSlot(slot);
    setPaso('datos');
  };

  const confirmar = async (nombre: string, telefono: string): Promise<boolean> => {
    const creada = await booking.reservar(nombre, telefono);
    if (creada) {
      setPaso('confirmacion');
    }
    return creada;
  };

  const volverAHorarios = () => {
    booking.limpiarError();
    setPaso('horario');
    void booking.buscarSlots();
  };

  const reiniciar = () => {
    booking.reiniciar();
    setPaso('practica');
  };

  return (
    <div className="booking-page">
      <h1>Reservar turno</h1>
      <p className="booking-intro">
        Elegí el tratamiento, buscá un horario libre y confirmá tus datos. No necesitás cuenta.
      </p>

      <div className="booking-steps">
        {PASOS.map((candidate, index) => (
          <div
            key={candidate.id}
            className={`step ${index <= pasoActual ? 'active' : ''}`}
            aria-current={candidate.id === paso ? 'step' : undefined}
          >
            <span className="step-number">{index + 1}</span>
            <span className="step-label">{candidate.label}</span>
          </div>
        ))}
      </div>

      {paso === 'practica' && (
        <PracticeStep
          practicas={booking.practicas}
          seleccionada={booking.practicaId}
          cargando={booking.cargandoPracticas}
          error={booking.error}
          onSelect={booking.setPracticaId}
          onContinuar={() => {
            booking.limpiarError();
            setPaso('horario');
          }}
          onReintentar={() => void booking.recargarPracticas()}
        />
      )}

      {paso === 'horario' && (
        <SlotStep
          fecha={booking.fecha}
          slots={booking.slots}
          cargando={booking.cargandoSlots}
          error={booking.error}
          onFechaChange={booking.setFecha}
          onBuscar={() => void booking.buscarSlots()}
          onSelect={elegirSlot}
          onVolver={() => setPaso('practica')}
        />
      )}

      {paso === 'datos' && booking.slotElegido && (
        <PatientStep
          slot={booking.slotElegido}
          practica={practicaSeleccionada}
          enviando={booking.enviando}
          error={booking.error}
          onConfirmar={confirmar}
          onVolver={volverAHorarios}
        />
      )}

      {paso === 'confirmacion' && booking.reserva && (
        <ConfirmationStep reserva={booking.reserva} onReiniciar={reiniciar} />
      )}
    </div>
  );
}
