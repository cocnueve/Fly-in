"""Fly-in Simulator Data Models.
This module defines the business objects used by the rest of the program:
zones (`Zone`), connections between zones (`Connection`), drones (`Drone`)
and the complete map graph (`Graph`). All of these objects are
PyDantic models, which allows for automatic validation of the values
read from the map file (coordinates, capacities, etc.).
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class ZoneType(Enum):
    """The type of a zone, which determines its accessibility and cost."""

    NORMAL = "normal"       # coût 1 tour
    BLOCKED = "blocked"     # inaccessible
    RESTRICTED = "restricted"  # coût 2 tours
    PRIORITY = "priority"   # coût 1 tour, préféré


class Zone(BaseModel):
    """An area (hub) on the map that can accommodate drones.

    Attributes:
        name: Unique identifier for the area (e.g., “start,” “goal”).
        x: X coordinate on the map.
        y: Y coordinate on the map.
        zone_type: Type of area (normal, blocked, restricted, priority).
        color: Display color (used by the viewer).
        max_drones: Maximum number of drones that can occupy the zone
            at the same time.
        current_drones: List of drones currently present in
            the zone.
        waiting: Number of drones currently waiting to enter
            the zone.
        temp_zone: Saves the original zone type when the zone
            is temporarily marked as BLOCKED (because it is full), so that
            it can be restored once a spot becomes available.
        temp_drone: Field reserved for future use (not currently
            used by the simulation logic).
    """

    name: str = Field(min_length=1, max_length=30)
    x: int = Field(ge=-30, le=30)
    y: int = Field(ge=-30, le=30)
    zone_type: ZoneType = Field(default=ZoneType.NORMAL)
    color: Optional[str] = Field(default=None)
    max_drones: Optional[int] = Field(default=1, ge=0, le=25)
    # drones présents ce tour
    current_drones: List["Drone"] = Field(default_factory=list)
    waiting: Optional[int] = Field(default=0, ge=0, le=1000)
    temp_zone: Optional["ZoneType"] = Field(default=None)
    temp_drone: Optional["Drone"] = Field(default=None)

    def is_accessible(self) -> int | None:
        """Indicates whether the area is passable and with what priority.

        Returns:
            0 if the area is blocked (inaccessible), 1 if it is
            restricted, 2 if it is normal, 3 if it has priority,
            or None if the area type is unknown.
        """
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
        """Indicates whether the area can still accommodate at least one drone."""
        if self.current_drones is None:
            return False
        if self.max_drones is None:
            return False
        if len(self.current_drones) >= self.max_drones:
            return False
        else:
            return True

    def add_drone(self, drone: Drone) -> int:
        """Attempts to have a drone enter the zone.

        The behavior depends on the zone's capacity,
        the status of the connection used by the drone, and the type of
        zone (normal, restricted, priority, etc.).

        Args:
            drone: The drone attempting to enter the zone.

        Returns:
            An integer code indicating the result of the attempt:
            0/False if entry is denied, 1 if the drone enters
            a restricted zone in transit, 2 or 3 if the drone enters
            a normal or priority zone directly.
        """
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
        """Removes a drone from the zone, if one is present there.

        If the zone was temporarily blocked because it was
        full, its original type is restored.

        Args:
            drone: The drone to remove from the zone.

        Returns:
            True if the drone was successfully removed, False if it was
            not present in the zone.
        """
        if drone in self.current_drones:
            self.current_drones.remove(drone)

            was_blocked = self.zone_type == ZoneType.BLOCKED
            if was_blocked and self.temp_zone is not None:
                self.zone_type = self.temp_zone

            return True
        else:
            return False

    def info(self) -> str:
        """Returns a human-readable description of the current state of the zone."""
        return (
            f"Name: {self.name}\nCoordinate: X={self.x}, Y={self.y}\
            \nZoneType: {self.zone_type}\
            \nMax drone authorized: {self.max_drones}\
            \nCurrent drones: {len(self.current_drones)}"
        )


class Connection(BaseModel):
    """A connection (route) between two zones in the graph.

    Attributes:
        zone_a: One of the two zones connected by the link.
        zone_b: The other zone connected by the link.
        max_link: The maximum number of drones that can use the
            link simultaneously.
        current_usage: The number of drones currently in transit on
            this link during the current turn.
    """

    zone_a: Zone
    zone_b: Zone
    max_link: Optional[int] = Field(default=1, ge=0, le=5)
    # drones en transit ce tour
    current_usage: Optional[int] = Field(default=0, ge=0, le=5)

    def conn_capacity(self) -> bool:
        """Indicates whether the connection can still accommodate a drone."""
        if self.max_link is None:
            return False
        if self.current_usage is None:
            return False
        if self.current_usage < self.max_link:
            return True
        else:
            return False

    def change_usage(self, order: int) -> None:
        """Updates the number of drones in transit on the connection.

        Args:
            order: 1 to increment a drone's current usage,
                0 to reset usage to zero (new round).
        """
        if self.current_usage is not None:
            if order == 1:
                self.current_usage += 1
            elif order == 0:
                self.current_usage = 0


class DroneState(Enum):
    """Current status of a drone in the simulation."""

    WAITING = "waiting"
    MOVING = "moving"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"


class Drone(BaseModel):
    """A drone that follows a path (`path`) from one zone to another.

    Attributes:
        drone_id: The drone's unique identifier.
        current_zone: The zone where the drone is currently located.
        next_zone: The next zone the drone is heading for along its path.
        path: An ordered list of the zones the drone must traverse,
            from the starting zone to the destination zone.
        path_index: Index of the drone’s current zone in `path`.
        state: Current state of the drone (moving, in transit,
            arrived...).
        remain: Counter used to determine whether the drone has already
            been counted in a zone’s queue.
        on_connection: Connection currently used by the drone,
            if applicable.
    """

    drone_id: int = Field(ge=0, le=25)
    current_zone: Zone
    next_zone: Optional[Zone] = Field(default=None)
    path: list[Zone]
    path_index: Optional[int] = Field(default=0, ge=0, le=1000)
    state: Optional[DroneState] = DroneState.MOVING
    remain: Optional[int] = Field(default=0, ge=0, le=10)
    on_connection: Optional[Connection] = Field(default=None)

    def has_arrived(self) -> bool:
        """Indicates whether the drone has reached the end of its path.

        Also updates `state` to `ARRIVED` if this is the case.

        Returns:
            True if the drone has reached the end of `path`, False otherwise.
        """
        if self.path_index is None:
            return False

        if self.path_index >= len(self.path) - 1:
            self.state = DroneState.ARRIVED
            return True
        else:
            return False

    def update_zone(self) -> self:
        """Updates `current_zone` and `next_zone` based on `path_index`.

        Does nothing if the drone has already reached the end of its path.

        Returns:
            The drone itself (to allow for call chaining).
        """
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
        """Searches for and stores the connection to the next zone.

        Args:
            graph: The graph containing the zones and connections.

        Returns:
            True if a connection was found and assigned to
            `on_connection`, False otherwise.
        """
        final_conn = self.update_conn(graph)
        if final_conn is None:
            return False
        else:
            self.on_connection = final_conn
            return True


class Graph(BaseModel):
    """The complete graph of the map: zones, connections, and metadata.

    Attributes:
        zones: A dictionary that associates the name of each zone with the corresponding
            `Zone` object.
        connections: A list of all connections between zones.
        nb_drones: Number of drones to fly on this map.
        start: Starting zone of the simulation, if it was found
            during parsing.
        end: Ending zone of the simulation, if it was found
            during parsing.
    """

    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    nb_drones: int = Field(default=0, ge=0, le=50)
    start: Optional[Zone] = Field(default=None)
    end: Optional[Zone] = Field(default=None)

    def get_neighbors(self, zone: Zone) -> list[tuple[Zone, Connection]]:
        """Returns the accessible neighboring zones along with their connections."""
        result = []
        for conn in self.connections:
            if conn.zone_a == zone:
                result.append((conn.zone_b, conn))
            elif conn.zone_b == zone:
                result.append((conn.zone_a, conn))
        return result
