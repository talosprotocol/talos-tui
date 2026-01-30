from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import jsonschema

logger = logging.getLogger(__name__)

class ContractValidator:
    """
    Mechanized contract validation using JSON schemas from talos-contracts.
    """
    
    def __init__(self, schemas_root: Path):
        self.schemas_root = schemas_root
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _load_schema(self, schema_path: str) -> Dict[str, Any]:
        if schema_path in self._cache:
            return self._cache[schema_path]
        
        full_path = self.schemas_root / schema_path
        if not full_path.exists():
            logger.error(f"Schema not found: {full_path}")
            raise FileNotFoundError(f"Schema {schema_path} not found at {full_path}")
            
        with open(full_path, "r") as f:
            schema = json.load(f)
            self._cache[schema_path] = schema
            return schema

    def validate(self, schema_path: str, data: Any) -> None:
        """
        Validate data against a schema. Throws jsonschema.ValidationError on failure.
        """
        try:
            schema = self._load_schema(schema_path)
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            logger.error(f"Contract validation failed for {schema_path}: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Error loading/validating schema {schema_path}: {e}")
            raise
