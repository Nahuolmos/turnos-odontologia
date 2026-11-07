"""Script de seed idempotente para C-02 y C-04.

Inserta:
- 1 Clínica (timezone AR, wa_sender Twilio, cuenta MP)
- 1 admin, 1 recepción, 1 odontólogo
- 2-3 sillones activos
- 5 prácticas odontológicas provisorias

Idempotente: ejecutar dos veces no duplica datos.
Contraseñas hasheadas con bcrypt (no texto plano).
"""

import asyncio
import os
import sys
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.domain.clinica.models import Clinic, Sillon
from app.domain.personas.models import User
from app.domain.turnos.models import TipoPractica
from app.infrastructure.db.base import Base

# Catálogo provisorio de prácticas. Duracion, precio y seña NO son datos del
# negocio: C-13 los reemplaza con el ABM real. Debe mantenerse alineado con
# PRACTICAS_SEED de la migración 004.
PRACTICAS_SEED: tuple[dict[str, Any], ...] = (
    {
        "id": UUID("00000000-0000-4000-8000-000000000001"),
        "nombre": "Limpieza",
        "duracion_min": 30,
        "precio_base": 15000,
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000002"),
        "nombre": "Arreglo",
        "duracion_min": 45,
        "precio_base": 25000,
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000003"),
        "nombre": "Endodoncia",
        "duracion_min": 60,
        "precio_base": 40000,
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000004"),
        "nombre": "Extracción",
        "duracion_min": 30,
        "precio_base": 20000,
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000005"),
        "nombre": "Ortodoncia control",
        "duracion_min": 20,
        "precio_base": 12000,
        "sena_pct": 30,
    },
)


async def seed_practicas(session: AsyncSession, clinic_id: UUID) -> None:
    """Insertar el catálogo provisorio para una clínica, sin duplicar.

    La primera clínica usa los UUID fijos del catálogo (los mismos de la
    migración 004). Las clínicas adicionales reciben UUID deterministas
    derivados de ``clinic_id`` + nombre para conservar la idempotencia.
    """
    primera_clinic_id = (
        await session.execute(
            select(Clinic.id).order_by(Clinic.created_at.asc(), Clinic.id.asc()).limit(1)
        )
    ).scalar_one_or_none()

    for practica in PRACTICAS_SEED:
        existente = await session.execute(
            select(TipoPractica.id).where(
                TipoPractica.clinic_id == clinic_id,
                TipoPractica.nombre == practica["nombre"],
            )
        )
        if existente.scalar_one_or_none() is not None:
            continue

        if clinic_id == primera_clinic_id:
            practica_id: UUID = practica["id"]
        else:
            practica_id = uuid5(
                NAMESPACE_URL,
                f"{clinic_id}:{practica['nombre']}",
            )

        session.add(
            TipoPractica(
                id=practica_id,
                clinic_id=clinic_id,
                nombre=practica["nombre"],
                duracion_min=practica["duracion_min"],
                precio_base=practica["precio_base"],
                sena_pct=practica["sena_pct"],
                activa=True,
                is_active=True,
            )
        )

    await session.flush()


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

    async with engine.begin() as conn:
        # Asegurar que las tablas existan (idem potencia con Alembic)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        # --- Clinic ---
        result = await session.execute(select(Clinic).limit(1))
        clinic = result.scalar_one_or_none()
        if clinic is None:
            clinic = Clinic(
                id=uuid4(),
                nombre="Clínica Odontológica Central",
                timezone="America/Argentina/Buenos_Aires",
                wa_sender="whatsapp:+5491100000000",
                mp_account="APP_USR-SEED-ACCOUNT",
                is_active=True,
            )
            session.add(clinic)
            await session.flush()

        # --- Users: admin, recepcion, odontólogo ---
        for email, password, rol in [
            ("admin@clinica.com", "Admin1234!", "admin"),
            ("recepcion@clinica.com", "Recepcion1234!", "recepcion"),
            ("odontologo@clinica.com", "Odonto1234!", "odonto"),
        ]:
            result = await session.execute(
                select(User).where(
                    User.clinic_id == clinic.id,  # type: ignore[attr-defined]
                    User.email == email,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    User(
                        id=uuid4(),
                        clinic_id=clinic.id,
                        email=email,
                        password_hash=hash_password(password),
                        rol=rol,
                        activo=True,
                        is_active=True,
                    )
                )

        await session.flush()

        # --- Sillones: 2-3 activos ---
        for nombre in ["Sillón 1", "Sillón 2", "Sillón 3"]:
            result = await session.execute(
                select(Sillon).where(
                    Sillon.clinic_id == clinic.id,  # type: ignore[attr-defined]
                    Sillon.nombre == nombre,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    Sillon(
                        id=uuid4(),
                        clinic_id=clinic.id,
                        nombre=nombre,
                        activo=True,
                        is_active=True,
                    )
                )

        await session.flush()

        # --- Prácticas: catálogo provisorio de 5 ---
        await seed_practicas(session, clinic.id)

        await session.commit()
        print(
            "✅ Seed completado: clínica, usuarios, sillones y prácticas "
            "insertados (idempotente)."
        )


if __name__ == "__main__":
    asyncio.run(seed())
