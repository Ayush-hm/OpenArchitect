from pydantic import BaseModel


class DiagramSpec(BaseModel):
    format: str = "mermaid"
    content: str

