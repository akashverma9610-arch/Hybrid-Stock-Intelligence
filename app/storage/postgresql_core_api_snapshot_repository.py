from __future__ import annotations
import json
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_dump, snapshot_json_from
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory


class PostgreSQLCoreApiSnapshotRepository:
    """Parameterized PostgreSQL adapter for immutable core API read snapshots."""
    def __init__(self, connections: DatabaseConnectionFactory) -> None:
        if connections.settings.backend is not DatabaseBackend.POSTGRESQL: raise ValueError("PostgreSQL core snapshots require DATABASE_BACKEND=postgresql.")
        self._connections=connections
    def save_snapshot(self,value: CoreApiSnapshot)->None:
        try:
            with self._connections.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("INSERT INTO core_api_snapshots (snapshot_id,family,schema_version,record_type,fingerprint,created_at,payload_json) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)", (value.snapshot_id,value.family.value,value.schema_version,value.record_type,value.fingerprint,value.created_at,json.dumps(snapshot_dump(value),sort_keys=True,separators=(",",":"))))
        except Exception as error:
            if getattr(error,"sqlstate",None)=="23505": raise ValueError("Core API snapshots are immutable and cannot be overwritten.") from error
            raise
    def get_snapshot(self,snapshot_id:str)->CoreApiSnapshot|None:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=%s",(snapshot_id,));row=cursor.fetchone()
        return snapshot_json_from(row[0]) if row else None
    def list_snapshots(self,family:CoreApiSnapshotFamily,*,limit:int=100,offset:int=0)->tuple[CoreApiSnapshot,...]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("Snapshot pagination is invalid.")
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM core_api_snapshots WHERE family=%s ORDER BY created_at,snapshot_id LIMIT %s OFFSET %s",(family.value,limit,offset));rows=cursor.fetchall()
        return tuple(snapshot_json_from(row[0]) for row in rows)
    def list_canonical_prospective_fifteen_minute_snapshots(self,canonical_security_id:str,*,known_at_lte:str|None,limit:int)->tuple[CoreApiSnapshot,...]:
        if not canonical_security_id or not 1<=limit<=100: raise ValueError("Prospective 15m snapshot query is invalid.")
        query="SELECT payload_json FROM core_api_snapshots WHERE family=%s AND payload_json->'payload'->'fields'->>'canonical_security_id'=%s"
        parameters:list[object]=[CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR.value,canonical_security_id]
        if known_at_lte is not None:
            query+=" AND payload_json->'payload'->'fields'->'known_at'->>'value'<=%s";parameters.append(known_at_lte)
        query+=" ORDER BY payload_json->'payload'->'fields'->'partition'->'fields'->'interval_start'->>'value' DESC,snapshot_id DESC LIMIT %s";parameters.append(limit)
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor: cursor.execute(query,tuple(parameters));rows=cursor.fetchall()
        return tuple(snapshot_json_from(row[0]) for row in rows)
    def list_canonical_prospective_fifteen_minute_conflicts(self,receipt_ids:tuple[str,...],*,detected_at_lte:str|None)->tuple[CoreApiSnapshot,...]:
        if not receipt_ids or len(receipt_ids)>100 or any(not value for value in receipt_ids): return ()
        query="SELECT payload_json FROM core_api_snapshots WHERE family=%s AND payload_json->'payload'->'fields'->>'receipt_id'=ANY(%s)"
        parameters:list[object]=[CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_CONFLICT.value,list(receipt_ids)]
        if detected_at_lte is not None:
            query+=" AND payload_json->'payload'->'fields'->'detected_at'->>'value'<=%s";parameters.append(detected_at_lte)
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query+" ORDER BY snapshot_id",tuple(parameters));rows=cursor.fetchall()
        return tuple(snapshot_json_from(row[0]) for row in rows)
