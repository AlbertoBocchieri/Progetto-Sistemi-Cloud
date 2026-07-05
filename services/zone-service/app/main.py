from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine


app = FastAPI(
    title="ParcheggIA Zone Service",
    description="Servizio geospaziale per la gestione delle zone urbane.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Verifica che il processo applicativo sia attivo.
    Non controlla le dipendenze esterne.
    """
    return {
        "status": "up",
        "service": "zone-service",
    }


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    """
    Verifica che il servizio possa comunicare con PostgreSQL/PostGIS.
    """
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
        # Il dettaglio completo viene scritto nei log del container,
        # ma non viene esposto al client.
        print(f"Database readiness check failed: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available",
        ) from error