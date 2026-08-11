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
    def __init__(self) -> None:
        pass

    def create_drone(self, id: int, start_zone: Zone, path: list[Zone]) -> Drone:
        return Drone(drone_id=id, current_zone=start_zone, path=path)


class Simulation:
    """Manage drone movement across the graph, turn by turn."""

    def __init__(self, graph: Graph, pathfinder: Pathfinder, drone_list: list[Drone], vis: Visualizer):
        self.graph = graph
        self.pathfinder = pathfinder
        self.drone_list = drone_list
        self.vis = vis

    def move_drone(self, drone: Drone) -> bool:

        if drone.path[drone.path_index] is not None:  # check that a previous zone exists.
            if drone.path_index < len(drone.path) - 1:
                current_zone = drone.path[drone.path_index]  # previous zone.
                next_zone = drone.path[drone.path_index + 1]
                if drone.check_conn(self.graph) is True:
                    assert drone.on_connection is not None  # guaranteed by check_conn() == True

                    if next_zone.is_accessible() == 1 and drone.state == DroneState.MOVING:
                        # restricted zone: also count drones already in flight toward it,
                        # not just the ones already arrived, so it isn't overbooked 2 turns ahead.
                        already_in_flight = sum(
                            1 for d in self.drone_list
                            if d.state == DroneState.IN_TRANSIT
                            and d.path_index < len(d.path) - 1
                            and d.path[d.path_index + 1] == next_zone
                        )
                        if len(next_zone.current_drones) + already_in_flight >= next_zone.max_drones:
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
        i = 0
        # main loop
        while any(drone.state != DroneState.ARRIVED for drone in self.drone_list):
            i += 1
            if i > 200:  # safety for dodge overflow.
                print("The program has been automaticly close, it overpassed the 200 tries.")
                sys.exit()
            turn_moves = []  # this turn's "D<id>-<zone>" list, for the text output (VII.5)
            for drone in self.drone_list:
                if drone.on_connection is not None:  # set connection pointed by the drone to 0.
                    drone.on_connection.change_usage(0)
                if drone.state == DroneState.ARRIVED:
                    continue

                if drone.path_index < len(drone.path) - 1:
                    drone.update_zone()  # update target zones of the drone.
                    assert drone.next_zone is not None  # guaranteed as long as the drone hasn't arrived
                    result = self.move_drone(drone)  # moves the drone and returns whether it worked.

                    if result is True:
                        label = drone.path[drone.path_index].name
                        turn_moves.append(f"D{drone.drone_id}-{label}")
                    elif drone.state == DroneState.IN_TRANSIT and drone.on_connection is not None:
                        # the drone is in flight toward a restricted zone (2 turns): show the connection
                        conn = drone.on_connection
                        turn_moves.append(f"D{drone.drone_id}-{conn.zone_a.name}-{conn.zone_b.name}")

                    if result is False:
                        if drone.remain < 1:  # If the drone isn't waiting yet, it joins the queue.
                            drone.next_zone.waiting += 1
                            drone.remain += 1

                        if drone.next_zone.waiting > 2:  # queue too long -> recompute a path
                            self.change_path(drone)
                            if drone.remain > 0:  # If the drone was waiting, it leaves the queue
                                drone.remain -= 1
                                drone.next_zone.waiting -= 1
                    elif result is True and drone.next_zone.waiting > 0 and drone.remain > 0:
                        # If the drone moved while it was in the queue, it leaves it
                        drone.remain -= 1
                        drone.next_zone.waiting -= 1
                else:  # If the drone reached the end of its path, it changes drone_state.
                    drone.state = DroneState.ARRIVED

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
        graph = parser.parse_file("/mnt/f/coc9/Documents/code/Fly-in/config.txt")
        assert graph.start is not None and graph.end is not None  # guaranteed by Parser.parse_file()
        pathfinded = pathfinder.find_shortest_path(graph, graph.start, graph.end)
        if pathfinded is None:
            print("Error: no path found between start and end.")
            sys.exit()
        fact = DroneFactory()
        drone_list = []
    except Exception:
        raise

    vis = Visualizer(graph)
    TOUR_DELAY = 0.7  # seconds between tours, purely so you can watch it happen

    # drone factory
    for i in range(graph.nb_drones):
        temp_drone = fact.create_drone(i + 1, graph.start, pathfinded)
        drone_list.append(temp_drone)

    # drone set-up
    for drone in drone_list:
        graph.start.add_drone(drone)

    simulation = Simulation(graph, pathfinder, drone_list, vis)
    simulation.run()
