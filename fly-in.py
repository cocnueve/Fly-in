"""Entry point: parses a map, then runs the turn-by-turn drone simulation."""
from __future__ import annotations
from system import ZoneType, Zone, Drone, DroneState, Graph
from parser import Parser
from visualizer import Visualizer
from typing import Optional
from dataclasses import dataclass, field
import heapq
import sys
import time


@dataclass(order=True)
class PathNode:
    """An entry in the Dijkstra priority queue.

    Only `cost` participates in comparisons (order=True + compare=False
    on the other fields), so heapq always pops the cheapest node next.
    """

    cost: int
    zone: Zone = field(compare=False)
    path: list[Zone] = field(compare=False, default_factory=list)


class Pathfinder:
    """Finds the optimal path in a zone graph."""

    def find_shortest_path(
        self,
        graph: Graph,
        start: Zone,
        end: Zone
    ) -> Optional[list[Zone]]:
        """Returns the lowest-cost path, or None if unreachable."""
        heap = [PathNode(0, start, [start])]
        visited: set[str] = set()

        while heap:
            node = heapq.heappop(heap)
            if node.zone.name in visited:
                continue
            visited.add(node.zone.name)

            if node.zone == end:
                return node.path

            for neighbor, conn in graph.get_neighbors(node.zone):
                if neighbor.name not in visited and neighbor.is_accessible():
                    cost = self._get_movement_cost(neighbor)
                    heapq.heappush(heap, PathNode(
                        node.cost + cost,
                        neighbor,
                        node.path + [neighbor]
                    ))
        return None  # no path found

    def _get_movement_cost(self, zone: Zone) -> int:
        """Returns the cost in turns to enter a zone."""
        if zone.zone_type == ZoneType.RESTRICTED:
            return 3
        elif zone.zone_type == ZoneType.BLOCKED:
            return 4
        elif zone.zone_type == ZoneType.PRIORITY:
            return 1
        else:
            return 2


class DroneFactory():
    """Builds Drone instances, keeping their creation logic in one place."""

    def __init__(self) -> None:
        pass

    def create_drone(
        self,
        id: int,
        start_zone: Zone,
        path: list[Zone]
    ) -> Drone:
        """Create a new drone starting at start_zone, following path.

        Args:
            id: The drone's unique identifier (used as D<id> in logs).
            start_zone: The zone the drone begins in (always graph.start).
            path: The full zone-by-zone route the drone will follow.

        Returns:
            The newly created Drone, in DroneState.MOVING.
        """
        return Drone(drone_id=id, current_zone=start_zone, path=path)


class Simulation:
    """Manage drone movement across the graph, turn by turn."""

    def __init__(
        self, graph: Graph, pathfinder: Pathfinder,
        drone_list: list[Drone], vis: Visualizer
    ):
        self.graph = graph
        self.pathfinder = pathfinder
        self.drone_list = drone_list
        self.vis = vis

    def move_drone(self, drone: Drone) -> bool:
        """Method that return a bool in function the drone moved"""
        if drone.path[drone.path_index] is not None:
            if drone.path_index < len(drone.path) - 1:
                current_zone = drone.path[drone.path_index]
                next_zone = drone.path[drone.path_index + 1]
                if drone.check_conn(self.graph) is True:
                    assert drone.on_connection is not None
                    if (
                        next_zone.is_accessible() == 1
                        and drone.state == DroneState.MOVING
                    ):
                        already_in_flight = sum(
                            1 for d in self.drone_list
                            if d.state == DroneState.IN_TRANSIT
                            and d.path_index < len(d.path) - 1
                            and d.path[d.path_index + 1] == next_zone
                        )
                        if (
                            len(next_zone.current_drones) + already_in_flight
                            >= next_zone.max_drones
                        ):
                            return False

                    result = next_zone.add_drone(drone)

                    if result == 0:
                        return False

                    if result == 1:
                        if drone.state == DroneState.IN_TRANSIT:
                            return False
                        elif drone.state == DroneState.MOVING:
                            drone.path_index += 1
                            drone.on_connection.change_usage(1)
                            current_zone.del_drone(drone)
                            return True

                    elif result == 2:
                        drone.path_index += 1
                        drone.on_connection.change_usage(1)
                        if current_zone is not None:
                            current_zone.del_drone(drone)
                        drone.state = DroneState.MOVING
                        return True

                    elif result == 3:
                        drone.path_index += 1
                        drone.on_connection.change_usage(1)
                        if current_zone is not None:
                            current_zone.del_drone(drone)
                        drone.state = DroneState.MOVING
                        return True

                    return False

        return False

    def change_path(self, drone: Drone) -> bool:
        """Recompute a fresh shortest path for a congested drone.

        Called once a drone's target zone has more than 2 drones
        queued, so it can re-route around the bottleneck instead of
        waiting indefinitely.

        Args:
            drone: The drone to re-route, starting from its current
                position in its old path.

        Returns:
            True and updates drone.path if a new path was found,
            False if the destination is now unreachable.
        """
        assert self.graph.end is not None  # guaranteed by Parser.parse_file()
        new_path = self.pathfinder.find_shortest_path(
            self.graph, drone.path[drone.path_index], self.graph.end
        )
        if new_path is not None:
            drone.path = new_path
            return True
        else:
            return False

    def run(self) -> None:
        """Drive the simulation until every drone reaches the end zone.

        Each iteration is one simulation turn: every drone attempts
        one move (or joins/leaves its target zone's waiting queue),
        the turn's moves are printed in the "D<id>-<zone>" format
        required by VII.5, and the visualizer is refreshed.
        """
        i = 0
        # main loop
        while (
            any(drone.state != DroneState.ARRIVED
                for drone in self.drone_list)
        ):
            i += 1
            if i > 200:
                print(
                    "The program has been automaticly close,"
                    " it overpassed the 200 tries."
                )
                sys.exit()
            turn_moves = []
            for drone in self.drone_list:
                if drone.on_connection is not None:
                    drone.on_connection.change_usage(0)
                if drone.state == DroneState.ARRIVED:
                    continue

                if drone.path_index < len(drone.path) - 1:
                    drone.update_zone()
                    assert drone.next_zone is not None
                    result = self.move_drone(drone)

                    if result is True:
                        label = drone.path[drone.path_index].name
                        turn_moves.append(f"D{drone.drone_id}-{label}")
                    elif (
                        drone.state == DroneState.IN_TRANSIT
                        and drone.on_connection is not None
                    ):
                        conn = drone.on_connection
                        turn_moves.append(
                            f"D{drone.drone_id}-"
                            f"{conn.zone_a.name}-{conn.zone_b.name}"
                            )

                    if result is False:
                        if drone.remain < 1:
                            drone.next_zone.waiting += 1
                            drone.remain += 1

                        if drone.next_zone.waiting > 2:
                            self.change_path(drone)
                            if drone.remain > 0:
                                drone.remain -= 1
                                drone.next_zone.waiting -= 1
                    elif (
                        result is True and drone.next_zone.waiting > 0
                        and drone.remain > 0
                    ):
                        drone.remain -= 1
                        drone.next_zone.waiting -= 1
                else:
                    drone.state = DroneState.ARRIVED
                drone.has_arrived()

            print(" ".join(turn_moves))
            self.vis.update(self.drone_list, i)
            time.sleep(TOUR_DELAY)

        self.vis.update(self.drone_list, i)
        print("\nAll drones arrived. Close the visualizer window to exit.")
        self.vis.wait_until_closed()


if __name__ == "__main__":
    # set-up program
    try:
        parser = Parser()
        pathfinder = Pathfinder()
        if len(sys.argv) <= 1:
            raise ValueError("no args detected")
        elif len(sys.argv) > 2:
            raise ValueError("too many args detected")
        graph = parser.parse_file(sys.argv[1])
        assert (
            graph.start is not None
            and graph.end is not None
        )
        pathfinded = pathfinder.find_shortest_path(
            graph, graph.start, graph.end
        )
        if pathfinded is None:
            print("Error: no path found between start and end.")
            sys.exit()
        fact = DroneFactory()
        drone_list = []
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    vis = Visualizer(graph)
    TOUR_DELAY = 0.7

    # drone factory
    for i in range(graph.nb_drones):
        temp_drone = fact.create_drone(i + 1, graph.start, pathfinded)
        drone_list.append(temp_drone)

    # drone set-up
    for drone in drone_list:
        graph.start.add_drone(drone)

    simulation = Simulation(graph, pathfinder, drone_list, vis)
    simulation.run()
