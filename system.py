from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class ZoneType(Enum):
    NORMAL = "normal"       # coût 1 tour
    BLOCKED = "blocked"     # inaccessible
    RESTRICTED = "restricted"  # coût 2 tours
    PRIORITY = "priority"   # coût 1 tour, préféré


class Zone(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    x: int = Field(ge=-30, le=30)
    y: int = Field(ge=-30, le=30)
    zone_type: ZoneType = Field(default=ZoneType.NORMAL)
    color: Optional[str] = Field(default=None)
    max_drones: int = Field(default=1, ge=0, le=25)
    current_drones: List["Drone"] = Field(default_factory=list)  # drones présents ce tour
    waiting: Optional[int] = Field(default=0, ge=0, le=1000)
    temp_zone: Optional["ZoneType"] = Field(default=None)
    temp_drone: Optional["Drone"] = Field(default=None)

    @model_validator(mode="after")
    def validator(self):
        return self

    def is_accessible(self) -> int | None:
        if self.zone_type == ZoneType.BLOCKED:
            return 0
        if self.zone_type == ZoneType.RESTRICTED:
            return 1
        if self.zone_type == ZoneType.NORMAL:
            return 2
        if self.zone_type == ZoneType.PRIORITY:
            return 3
        else:
            return None

    def has_capacity(self) -> bool:
        if self.current_drones is None:
            return False
        if self.max_drones is None:
            return False
        if len(self.current_drones) >= self.max_drones:
            return False
        else:
            return True

    def add_drone(self, drone: Drone) -> int:
        if self.has_capacity():
            result = self.is_accessible()
            if drone.on_connection is not None:
                if drone.on_connection.conn_capacity() is False:
                    return False
            if result is None:
                return False

            if self.current_drones is None:
                return False

            if result > 1:
                self.current_drones.append(drone)
                if self.has_capacity() is False:
                    self.temp_zone = self.zone_type
                    self.zone_type = ZoneType.BLOCKED
                return result

            elif result == 1 and drone.state == DroneState.MOVING:
                drone.state = DroneState.IN_TRANSIT
                return result
            elif drone.state == DroneState.IN_TRANSIT:
                drone.state = DroneState.MOVING
                self.current_drones.append(drone)
                return result
            else:
                return 0
        else:
            return False

    def del_drone(self, drone: Drone) -> bool:
        if drone in self.current_drones:
            self.current_drones.remove(drone)

            if self.zone_type == ZoneType.BLOCKED and self.temp_zone is not None:
                self.zone_type = self.temp_zone

            return True
        else:
            return False

    def info(self) -> str:
        return (
            f"Name: {self.name}\nCoordinate: X={self.x}, Y={self.y}\
            \nZoneType: {self.zone_type}\nMax drone authorized: {self.max_drones}\
            \nCurrent drones: {len(self.current_drones)}"
        )


class Connection(BaseModel):
    zone_a: Zone
    zone_b: Zone
    max_link: Optional[int] = Field(default=1, ge=0, le=5)
    current_usage: Optional[int] = Field(default=0, ge=0, le=5)  # drones en transit ce tour

    @model_validator(mode="after")
    def check_all(self):
        if not self.conn_capacity():
            raise ValueError("Too many drones in the area.")
        return self

    def conn_capacity(self) -> bool:
        if self.max_link is None:
            return False
        if self.current_usage is None:
            return False
        if self.current_usage < self.max_link:
            return True
        else:
            return False

    def change_usage(self, order: int) -> None:
        if self.current_usage is not None:
            if order == 1:
                self.current_usage += 1
            elif order == 0:
                self.current_usage = 0


class DroneState(Enum):
    WAITING = "waiting"
    MOVING = "moving"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"


class Drone(BaseModel):
    drone_id: int = Field(ge=0, le=25)
    current_zone: Zone
    next_zone: Optional[Zone] = Field(default=None)
    path: list[Zone]
    path_index: Optional[int] = Field(default=0, ge=0, le=1000)
    state: Optional[DroneState] = DroneState.MOVING
    remain: Optional[int] = Field(default=0, ge=0, le=10)
    on_connection: Optional[Connection] = Field(default=None)

    def has_arrived(self) -> bool:
        if self.path_index is None:
            return False

        if self.path_index >= len(self.path) - 1:
            self.state = DroneState.ARRIVED
            return True
        else:
            return False

    def update_zone(self):
        if self.has_arrived() is False:
            self.current_zone = self.path[self.path_index]
            self.next_zone = self.path[self.path_index + 1]
        return self

    def update_conn(self, graph: Graph) -> Connection | None:
        """Return the connection between the current zone and the next zone.

        This method retrieves the neighbors of the current zone, updates the
        object's current zone by calling `update_zone()`, and searches for the
        connection linking the previous current zone to the next zone.

        Args:
            graph: The graph containing the zones and their connections.

        Returns:
            The connection between the current zone and the next zone if one
            exists, otherwise `None`.
        """
        next_conn = graph.get_neighbors(self.current_zone)
        self.update_zone()
        final_conn = None

        for zone, conn in next_conn:
            if conn.zone_a == self.current_zone:
                if conn.zone_b == self.next_zone:
                    final_conn = conn
            elif conn.zone_b == self.current_zone:
                if conn.zone_a == self.next_zone:
                    final_conn = conn
        return final_conn

    def check_conn(self, graph: "Graph") -> bool:
        final_conn = self.update_conn(graph)
        if final_conn is None:
            return False
        else:
            self.on_connection = final_conn
            return True


class Graph(BaseModel):
    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    nb_drones: Optional[int] = Field(ge=0, le=50, default=None)
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
