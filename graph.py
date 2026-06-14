from pydantic import BaseModel, Field, model_validator
from zone import Zone, Connection
from typing import Optional

class Graph(BaseModel):
    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    start: Optional[Zone] = Field(default=None)
    end: Optional[Zone] = Field(default=None)

    def get_neighbors(self, zone: Zone) -> list[tuple[Zone, Connection]]:
        """Retourne les zones voisines accessibles avec leur connexion."""
        result = []
        for conn in self.connections:
            if conn.zone_a == zone:
                result.append((conn.zone_b, conn))
            elif conn.zone_b == zone:
                result.append((conn.zone_a, conn))
        return result