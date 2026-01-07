"""
Data type definitions for tool input/output validation
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Union
import base64
from pathlib import Path

class DataType(Enum):
    """Supported data types for tool I/O"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    JSON = "json"
    CODE = "code"
    FILE = "file"
    STRUCTURED_DATA = "structured_data"
    EMBEDDING = "embedding"
    BINARY = "binary"

@dataclass
class DataFormat:
    """Detailed format specification"""
    type: DataType
    mime_type: str | None = None
    schema: dict | None = None  # For JSON/structured data
    language: str | None = None  # For code
    
    def __str__(self):
        if self.mime_type:
            return f"{self.type.value} ({self.mime_type})"
        if self.language:
            return f"{self.type.value} ({self.language})"
        return self.type.value

# Common format presets
class DataFormats:
    """Pre-defined common formats"""
    
    # Text formats
    TEXT_PLAIN = DataFormat(DataType.TEXT, "text/plain")
    TEXT_MARKDOWN = DataFormat(DataType.TEXT, "text/markdown")
    TEXT_HTML = DataFormat(DataType.TEXT, "text/html")
    
    # Image formats
    IMAGE_PNG = DataFormat(DataType.IMAGE, "image/png")
    IMAGE_JPEG = DataFormat(DataType.IMAGE, "image/jpeg")
    IMAGE_WEBP = DataFormat(DataType.IMAGE, "image/webp")
    IMAGE_BASE64 = DataFormat(DataType.IMAGE, "image/base64")
    
    # Audio formats
    AUDIO_WAV = DataFormat(DataType.AUDIO, "audio/wav")
    AUDIO_MP3 = DataFormat(DataType.AUDIO, "audio/mp3")
    
    # Code formats
    CODE_PYTHON = DataFormat(DataType.CODE, language="python")
    CODE_JAVASCRIPT = DataFormat(DataType.CODE, language="javascript")
    CODE_JSON = DataFormat(DataType.JSON, "application/json")
    
    # Structured
    STRUCTURED_DICT = DataFormat(DataType.STRUCTURED_DATA, schema={"type": "dict"})
    STRUCTURED_LIST = DataFormat(DataType.STRUCTURED_DATA, schema={"type": "list"})

class DataValidator:
    """Validate data matches expected format"""
    
    @staticmethod
    def validate(data: Any, expected_format: DataFormat) -> bool:
        """Check if data matches format"""
        
        if expected_format.type == DataType.TEXT:
            return isinstance(data, str)
        
        elif expected_format.type == DataType.IMAGE:
            # Check if base64 string or file path or bytes
            if isinstance(data, str):
                # Check if base64
                if expected_format.mime_type == "image/base64":
                    try:
                        base64.b64decode(data)
                        return True
                    except:
                        pass
                # Check if file path
                return Path(data).suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']
            elif isinstance(data, bytes):
                return True
            return False
        
        elif expected_format.type == DataType.JSON:
            return isinstance(data, (dict, list))
        
        elif expected_format.type == DataType.CODE:
            return isinstance(data, str)
        
        elif expected_format.type == DataType.STRUCTURED_DATA:
            if expected_format.schema:
                schema_type = expected_format.schema.get("type")
                if schema_type == "dict":
                    return isinstance(data, dict)
                elif schema_type == "list":
                    return isinstance(data, list)
            return isinstance(data, (dict, list))
        
        return True  # Default: accept anything
    
    @staticmethod
    def convert(data: Any, from_format: DataFormat, to_format: DataFormat) -> Any:
        """Try to convert data between formats"""
        
        # Text conversions
        if from_format.type == DataType.TEXT and to_format.type == DataType.TEXT:
            return data  # Text to text is passthrough
        
        # JSON to text
        if from_format.type == DataType.JSON and to_format.type == DataType.TEXT:
            import json
            return json.dumps(data, indent=2)
        
        # Text to JSON
        if from_format.type == DataType.TEXT and to_format.type == DataType.JSON:
            import json
            try:
                return json.loads(data)
            except:
                return {"text": data}  # Wrap as object
        
        # Image conversions
        if from_format.type == DataType.IMAGE and to_format.type == DataType.IMAGE:
            # Image format conversions would go here
            # For now, passthrough
            return data
        
        # Can't convert, return as-is
        return data