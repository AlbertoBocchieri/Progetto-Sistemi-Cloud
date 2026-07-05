from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.schemas import ZoneResponse


app = FastAPI(
    title="ParcheggIA Zone Service",
    description="Servizio geospaziale per la gestione delle zone urbane.",
    version="0.2.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Verifica che il processo applicativo sia attivo."""
    return {
        "status": "up",
        "service": "zone-service",
    }


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    """Verifica la connessione a PostgreSQL e PostGIS."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

            postgis_version = connection.execute(
                text("SELECT PostGIS_Version()")
            ).scalar_one()

        return {
            "status": "ready",
            "database": "up",
            "postgis_version": postgis_version,
        }

    except SQLAlchemyError as error:
        print(f"Database readiness check failed: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available",
        ) from error


@app.get("/zones", response_model=list[ZoneResponse])
def get_zones() -> list[ZoneResponse]:
    """Restituisce tutte le zone disponibili come geometrie GeoJSON."""
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        name,
                        city,
                        zone_type,
                        baseline_capacity_estimate,
                        ST_AsGeoJSON(polygon)::json AS geometry
                    FROM zones
                    ORDER BY name
                    """
                )
            ).mappings().all()

        return [
            ZoneResponse(**dict(row))
            for row in rows
        ]

    except SQLAlchemyError as error:
        print(f"Unable to load zones: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load zones",
        ) from error