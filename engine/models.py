"""The one base model for everything typed in this engine.

Config sections, the run summary, and every payload sent over the wire all
derive from StrictModel. Unknown fields are an error everywhere, so a typo in
a config file and a stray key in an HTTP body fail the same way.
"""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
