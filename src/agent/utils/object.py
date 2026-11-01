from pydantic import BaseModel, ConfigDict, Field
from typing import List

## State Creation
class Analyst(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affiliation: str = Field(description="Primary affiliation ofthe analyst.")
    name: str = Field(description="Name of the analyst.")
    role: str = Field(description="Role of the analyst in the context of the topic.")
    description: str = Field(
        description="Description of the analyst focus, concerns, and motives."
    )

    @property
    def persona(self) -> str:
        return f"Name: {self.name}\nRole: {self.role}\nAffiliation: {self.affiliation}\nDescription: {self.description}\n"


class Perspectives(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysts: List[Analyst] = Field(
        description="Comprehensive list of analysts with their roles and affiliations."
    )