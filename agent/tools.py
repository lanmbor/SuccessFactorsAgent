# agent/tools.py
import json
import httpx
from lxml import etree
from sf.client import SFClient


async def sf_list_entities(client: SFClient) -> str:
    xml_text = await client.get_metadata()
    root = etree.fromstring(xml_text.encode())
    entity_sets = root.xpath("//*[local-name()='EntitySet']")
    names = sorted(es.get("Name") for es in entity_sets if es.get("Name"))
    return "\n".join(names) if names else "No entity sets found."


async def sf_get_schema(client: SFClient, entity_name: str) -> str:
    xml_text = await client.get_metadata()
    root = etree.fromstring(xml_text.encode())
    matches = root.xpath("//*[local-name()='EntityType'][@Name=$name]", name=entity_name)
    if not matches:
        return f"Entity '{entity_name}' not found in metadata."
    entity_type = matches[0]
    key_refs = entity_type.xpath(".//*[local-name()='PropertyRef']/@Name")
    key_names = set(key_refs)
    props = entity_type.xpath(".//*[local-name()='Property']")
    lines = []
    for p in props:
        name = p.get("Name", "")
        ptype = p.get("Type", "")
        nullable = p.get("Nullable", "true")
        marker = " [KEY]" if name in key_names else ""
        lines.append(f"  {name}: {ptype}{marker} nullable={nullable}")
    return f"Entity: {entity_name}\nProperties:\n" + "\n".join(lines)


async def sf_query(client: SFClient, entity_name: str, **kwargs) -> str:
    try:
        result = await client.query(entity_name, **kwargs)
        return json.dumps(result, indent=2)
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return f"Query error: {e}"


async def sf_create(client: SFClient, entity_name: str, data: dict) -> str:
    try:
        result = await client.create(entity_name, data)
        return json.dumps(result, indent=2)
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return f"Create error: {e}"


async def sf_update(client: SFClient, entity_name: str, key: str, data: dict) -> str:
    try:
        await client.update(entity_name, key, data)
        return "Updated successfully."
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return f"Update error: {e}"


async def sf_delete(client: SFClient, entity_name: str, key: str) -> str:
    try:
        await client.delete(entity_name, key)
        return "Deleted successfully."
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return f"Delete error: {e}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sf_list_entities",
            "description": "List all available SuccessFactors OData entity sets. Call this first when unsure what entities exist.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sf_get_schema",
            "description": "Get field names, types, and key properties for a SuccessFactors entity. Call this before querying to know the correct field names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "OData entity type name, e.g. 'PerPerson', 'EmpJob'"},
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sf_query",
            "description": "Query SuccessFactors OData entity records. Supports OData $filter, $select, $top, $skip, $expand, $orderby.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "OData entity type name, e.g. 'PerPerson', 'EmpJob'"},
                    "filter": {"type": "string", "description": "OData $filter, e.g. \"department eq 'Engineering'\""},
                    "select": {"type": "string", "description": "Comma-separated field names"},
                    "top": {"type": "integer", "description": "Max records to return"},
                    "skip": {"type": "integer", "description": "Records to skip for pagination"},
                    "expand": {"type": "string", "description": "Navigation properties to expand"},
                    "orderby": {"type": "string", "description": "Sort field, e.g. 'lastName asc'"},
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sf_create",
            "description": "Create a new record in a SuccessFactors entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "OData entity type name, e.g. 'PerPerson', 'EmpJob'"},
                    "data": {"type": "object", "description": "Field values for the new record"},
                },
                "required": ["entity_name", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sf_update",
            "description": "Update fields on an existing SuccessFactors record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "OData entity type name, e.g. 'PerPerson', 'EmpJob'"},
                    "key": {"type": "string", "description": "OData key, e.g. \"userId='U001'\" or composite \"userId='U001',startDate=datetime'2024-01-01T00:00:00'\""},
                    "data": {"type": "object", "description": "Fields and values to update"},
                },
                "required": ["entity_name", "key", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sf_delete",
            "description": "Delete a record from a SuccessFactors entity. Only call after summarizing what will be deleted and confirming with the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "OData entity type name, e.g. 'PerPerson', 'EmpJob'"},
                    "key": {"type": "string", "description": "OData key string, e.g. \"userId='U001'\""},
                },
                "required": ["entity_name", "key"],
            },
        },
    },
]
