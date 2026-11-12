from pydantic import BaseModel, ConfigDict, Field


class ToolManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    category: str
    icon: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    enabled_by_default: bool = True
