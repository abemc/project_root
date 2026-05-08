"""JSON schema for project analyzer output (simplified).
"""
JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "project_summary": {
            "type": "object",
            "properties": {
                "total_files": {"type": "integer"},
                "top_languages": {"type": "array"},
            },
            "required": ["total_files"]
        },
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "size": {"type": "integer"},
                    "lang": {"type": "string"},
                    "snippet": {"type": ["string", "null"]},
                    "sha256": {"type": ["string", "null"]},
                    "is_large": {"type": "boolean"},
                },
                "required": ["path", "size", "lang"]
            }
        }
    },
    "required": ["project_summary", "files"]
}


def get_schema() -> dict:
    return JSON_SCHEMA
