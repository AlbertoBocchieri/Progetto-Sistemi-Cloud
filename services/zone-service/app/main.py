from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.schemas import ZoneResponse


app = FastAPI(
    title="ParcheggIA Zone Service",
    description="Servizio geospaziale per la gestione delle zone urbane.",
    version="0.3.0",
)


def row_to_zone(row: Any) -> ZoneResponse:
    """Converte una riga restituita da SQLAlchemy in una risposta API."""
    return ZoneResponse(**dict(row))


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "up",
        "service": "zone-service",
    }


@app.get("/ready")
def readiness_check() -> dict[str, str]:
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
    """Restituisce tutte le zone disponibili."""
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

        return [row_to_zone(row) for row in rows]

    except SQLAlchemyError as error:
        print(f"Unable to load zones: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load zones",
        ) from error


@app.get("/zones/current", response_model=ZoneResponse)
def get_current_zone(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> ZoneResponse:
    """
    Restituisce la zona che contiene le coordinate indicate.

    Attenzione: PostGIS usa l'ordine longitudine, latitudine.
    """
    try:
        with engine.connect() as connection:
            row = connection.execute(
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
                    WHERE ST_Covers(
                        polygon,
                        ST_SetSRID(
                            ST_MakePoint(:lon, :lat),
                            4326
                        )
                    )
                    LIMIT 1
                    """
                ),
                {
                    "lat": lat,
                    "lon": lon,
                },
            ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No zone contains the specified coordinates",
            )

        return row_to_zone(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Unable to determine current zone: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to determine current zone",
        ) from error


@app.get("/zones/{zone_id}", response_model=ZoneResponse)
def get_zone_by_id(zone_id: str) -> ZoneResponse:
    """Restituisce una singola zona tramite identificativo."""
    try:
        with engine.connect() as connection:
            row = connection.execute(
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
                    WHERE id = :zone_id
                    """
                ),
                {
                    "zone_id": zone_id,
                },
            ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

        return row_to_zone(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Unable to load zone {zone_id}: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load zone",
        ) from error