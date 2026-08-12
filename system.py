"""Domain model for Fly-in: Zone, Connection, Drone and Graph."""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class ZoneType(Enum):
    """The four zone categories defined by the map format (VII.3).

    Each type carries a different movement cost and accessibility
    rule, applied when a drone attempts to enter the zone.
    """

    NORMAL = "normal"       # cost: 1 turn
    BLOCKED = "blocked"     # inaccessible
    RESTRICTED = "restricted"  # cost: 2 turns
    PRIORITY = "priority"   # cost: 1 turn, preferred


class Zone(BaseModel):
    """A single zone (hub) of the map, and its live occupancy state.

    Combines the static data coming from the map file (position,
    type, color, capacity) with the mutable state tracked during the
    simulation (drones currently inside, waiting queue).
    """

    name: str = Field(min_length=1, max_length=30)
    x: int = Field(ge=-30, le=30)
    y: int = Field(ge=-30, le=30)
    zone_type: ZoneType = Field(default=ZoneType.NORMAL)
    color: Optional[str] = Field(default=None)
    max_drones: int = Field(default=1, ge=1, le=25)
    current_drones: List["Drone"] = Field(default_factory=list)
    waiting: int = Field(default=0, ge=0, le=1000)
    temp_zone: Optional["ZoneType"] = Field(default=None)
    temp_drone: Optional["Drone"] = Field(default=None)

    @model_validator(mode="after")
    def validator(self) -> "Zone":
        """Run after Pydantic's field validation, currently a no-op hook.

        Kept as an extension point for future cross-field checks on
        the zone (e.g. consistency between zone_type and max_drones).
        """
        return self

    def is_accessible(self) -> int | None:
        """Return an accessibility code based on the zone's type.

        Used both by the pathfinder (to exclude blocked zones) and by
        add_drone (to pick the right entry behaviour, e.g. the 2-turn
        transit for restricted zones).

        Returns:
            0 for a blocked zone (never enterable), 1 for a restricted
            zone (multi-turn transit), 2 for a normal zone, 3 for a
            priority zone, or None if the zone_type is unrecognized.
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
        """Return whether the zone can still accept at least one drone.

        Compares the number of drones currently inside against
        max_drones (VII.2).
        """
        if self.current_drones is None:
            return False
        if self.max_drones is None:
            return False
        if len(self.current_drones) >= self.max_drones:
            return False
        else:
            return True

    def add_drone(self, drone: Drone) -> int:
        """Attempt to place a drone into this zone.

        Applies the accessibility rules from is_accessible(): normal
        and priority zones accept the drone directly, a restricted
        zone first puts the drone into DroneState.IN_TRANSIT for one
        turn before it actually enters, and a blocked zone (or a full
        zone) refuses the drone. Also marks the zone as temporarily
        BLOCKED once it reaches max_drones, so it stops accepting new
        drones until one leaves (see del_drone).

        Args:
            drone: The drone attempting to enter the zone.

        Returns:
            An int code consumed by Simulation.move_drone: 0 or False
            means refused, 1 means the drone started a restricted-zone
            transit, 2/3 mean the drone entered directly (normal /
            priority).
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
        """Remove a drone from the zone once it moves onward.

        If the zone had been temporarily marked BLOCKED because it
        was full (see add_drone), restores its real zone_type now
        that a spot has freed up.

        Args:
            drone: The drone leaving the zone.

        Returns:
            True if the drone was found and removed, False otherwise.
        """
        if drone in self.current_drones:
            self.current_drones.remove(drone)

            if (
                self.zone_type == ZoneType.BLOCKED
                and self.temp_zone is not None
            ):
                self.zone_type = self.temp_zone

            return True
        else:
            return False

    def info(self) -> str:
        """Return a human-readable multi-line summary of the zone's state.

        Used for the live-coding requirement mentioned in todo.txt:
        displaying a zone's info and its current drone count.
        """
        return (
            f"Name: {self.name}\nCoordinate: X={self.x}, Y={self.y}\
            \nZoneType: {self.zone_type}\nMax drone authorized: \
            {self.max_drones}\
            \nCurrent drones: {len(self.current_drones)}"
        )


class Connection(BaseModel):
    """A bidirectional edge linking two zones, with a capacity limit.

    max_link_capacity (VII.2) caps how many drones may be in transit
    on this connection during the same turn.
    """

    zone_a: Zone
    zone_b: Zone
    max_link: int = Field(default=1, ge=1, le=5)
    current_usage: int = Field(default=0, ge=0, le=5)

    @model_validator(mode="after")
    def check_all(self) -> "Connection":
        """Reject a Connection built with usage already over max_link."""
        if not self.conn_capacity():
            raise ValueError("Too many drones in the area.")
        return self

    def conn_capacity(self) -> bool:
        """Return whether the connection still has room for one more drone."""
        if self.max_link is None:
            return False
        if self.current_usage is None:
            return False
        if self.current_usage < self.max_link:
            return True
        else:
            return False

    def change_usage(self, order: int) -> None:
        """Update how many drones are currently transiting this connection.

        Args:
            order: 1 to record one more drone entering the connection
                this turn, 0 to reset the usage back to zero (called
                at the start of each turn in Simulation.run).
        """
        if self.current_usage is not None:
            if order == 1:
                self.current_usage += 1
            elif order == 0:
                self.current_usage = 0


class DroneState(Enum):
    """The lifecycle states a drone moves through during the simulation.

    IN_TRANSIT specifically marks the intermediate turn spent crossing
    a restricted zone's connection (VII.3): the drone has left its
    origin zone but hasn't entered the restricted zone yet.
    """

    WAITING = "waiting"
    MOVING = "moving"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"


class Drone(BaseModel):
    """A single drone: its identity, its target path, and its live state."""

    drone_id: int = Field(ge=0, le=25)
    current_zone: Zone
    next_zone: Optional[Zone] = Field(default=None)
    path: list[Zone]
    path_index: int = Field(default=0, ge=0, le=1000)
    state: DroneState = Field(default=DroneState.MOVING)
    remain: int = Field(default=0, ge=0, le=10)
    on_connection: Optional[Connection] = Field(default=None)

    def has_arrived(self) -> bool:
        """Check if the drone reached the end of its path.

        Also sets state to DroneState.ARRIVED as a side effect when
        that's the case, so callers don't need a separate assignment.
        """
        if self.path_index is None:
            return False

        if self.path_index >= len(self.path) - 1:
            self.state = DroneState.ARRIVED
            return True
        else:
            return False

    def update_zone(self) -> "Drone":
        """Sync current_zone/next_zone with the drone's path_index.

        No-op if the drone has already arrived, since there is no
        next_zone left to point to.
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
        self.update_zone()
        next_conn = graph.get_neighbors(self.current_zone)
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
        """Locate and cache the connection toward the drone's next zone.

        Args:
            graph: The graph to search for the connection.

        Returns:
            True and sets self.on_connection if a connection was
            found, False (leaving on_connection untouched) otherwise.
        """
        final_conn = self.update_conn(graph)
        if final_conn is None:
            return False
        else:
            self.on_connection = final_conn
            return True


class Graph(BaseModel):
    """The full map: every zone, every connection, and the drone count.

    Built by Parser.parse_file() from a map file and then used by
    both the Pathfinder and the Simulation.
    """

    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    nb_drones: int = Field(default=0, ge=0, le=50)
    start: Optional[Zone] = Field(default=None)
    end: Optional[Zone] = Field(default=None)

    def get_neighbors(self, zone: Zone) -> list[tuple[Zone, Connection]]:
        """Returns the accessible neighboring zones with their connection."""
        result = []
        for conn in self.connections:
            if conn.zone_a == zone:
                result.append((conn.zone_b, conn))
            elif conn.zone_b == zone:
                result.append((conn.zone_a, conn))
        return result
