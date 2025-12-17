from datetime import datetime
from neo4j.time import DateTime


def serialize_record(obj):
    """
    Convert Neo4j DateTime / datetime objects into JSON-safe formats
    """
    if isinstance(obj, list):
        return [serialize_record(i) for i in obj]

    if isinstance(obj, dict):
        return {k: serialize_record(v) for k, v in obj.items()}

    if isinstance(obj, (datetime, DateTime)):
        return obj.isoformat()

    return obj
