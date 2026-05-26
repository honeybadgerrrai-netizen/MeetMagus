"""Returns table_args dict with schema only when using Postgres."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dealflow.db")
IS_POSTGRES = not DATABASE_URL.startswith("sqlite")

def global_schema():
    return {"schema": "global"} if IS_POSTGRES else {}

def platform_schema():
    return {"schema": "platform"} if IS_POSTGRES else {}

def tenant_fk(col):
    """For cross-schema FKs: use schema-qualified name only on Postgres."""
    return col if IS_POSTGRES else col.split(".")[-1]
