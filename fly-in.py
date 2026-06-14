from zone import ZoneType, Zone, Connection, Drone, DroneState
from graph import Graph
from parser import Parser
from typing import Callable
import heapq
from dataclasses import dataclass, field
from typing import Optional

@dataclass(order=True)
class PathNode:
    cost: int
    zone: Zone = field(compare=False)
    path: list[Zone] = field(compare=False, default_factory=list)

class Pathfinder:
    """Trouve le chemin optimal dans un graphe de zones."""

    def find_shortest_path(
        self,
        graph: Graph,
        start: Zone,
        end: Zone
    ) -> Optional[list[Zone]]:
        """Retourne le chemin de coût minimal, ou None si impossible."""
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
        return None  # pas de chemin

    def _get_movement_cost(self, zone: Zone) -> int:
        """Retourne le coût en tours pour entrer dans une zone."""
        if zone.zone_type == ZoneType.RESTRICTED:
            return 2
        return 1  # normal et priority

class DroneFactory():
    def __init__(self):
        pass

    def create_drone(self, id: int, start_zone: Callable, path: list[Zone]):
        return Drone(drone_id=id, current_zone=start_zone, path=path)

sec = 0

def move_drone(drone: Callable) -> bool:
    old_zone = None
    global sec
    if drone.path_index >= len(drone.path):  ## VERIF si l'index du chemin est egale ou plus grand que le chemin le drone est arrive
        drone.state = DroneState.ARRIVED
        return

    if drone.path[drone.path_index - 1] is not None:  ## verif qu'il existe une zone precedante.
        if drone.path_index > 0:  ## verif que la zone precedante soit detectable a la 2e iteration.
            old_zone = drone.path[drone.path_index - 1]  ##zone precedante.

    if drone.path[drone.path_index] is not None:
        zone = drone.path[drone.path_index]
        result = zone.add_drone(drone)

    if result == 3 and sec == 0:
        drone.path_index += 1
        if old_zone is not None:
            old_zone.del_drone()

    elif result == 0 and sec == 0:
        return False

    elif result == 1 or sec == 1:
        if sec == 1:
            sec = 0
            drone.state = DroneState.WAITING
            drone.path_index += 1
        else:
            sec = 1
            drone.state = DroneState.IN_TRANSIT

        if old_zone is not None:
            old_zone.del_drone()

    elif result == 2 and sec == 0:
        drone.path_index += 1
        if old_zone is not None:
            old_zone.del_drone()

    return True

# def change_path(graph_values: list, drone: Drone) -> Zone:
#     pathfinder = Pathfinder()
#     for zone1 in graph_values:
#         zone1_data = (zone1.x, zone1.y)
#         for zone2 in drone.path[drone.path_index:]:
#             zone2_data = (zone2.x, zone2.y)
#             print(f"zone 1:{zone1_data}")
#             print(f"zone 2: {zone2_data}")
#             if zone1_data == zone2_data:
#                 print(f"\nSUCCES zone, find another way in the path\n D{drone.drone_id} go to {zone2.name}")
#                 return zone1
#             else:
#                 print("\nany zone finded.\n")


if __name__ == "__main__":
    parser = Parser()
    pathfinder = Pathfinder()
    graph = parser.parse_file("/home/ffeder/Desktop/3e cercle/fly-in/config.txt")
    pathfinded = pathfinder.find_shortest_path(graph, graph.zones["zone_1"], graph.zones["zone_2"])
    fact = DroneFactory()
    drone_list = []


    for i in range(1, 6):
        temp_drone = fact.create_drone(i, graph.zones["zone_1"], pathfinded)
        drone_list.append(temp_drone)
    old_zone = None
    i = 0


    while any(drone.state != DroneState.ARRIVED for drone in drone_list):
        i += 1
        print(f"\n=== TOUR {i}===\n")
        for drone in drone_list:
            if drone.state == DroneState.ARRIVED:
                continue

            if drone.path_index < len(drone.path):
                print(
                    f"\nD{drone.drone_id}-{drone.path[drone.path_index].name}"
                )

            result = move_drone(drone)
            if result is False:
                drone.path[drone.path_index].waiting += 1
                graph_zones = graph.zones.values()
                current_zone = drone.path[drone.path_index]
                print(f"Drone wait for the {current_zone.name}: {current_zone.waiting}")
                if current_zone.waiting > 3:
                    print("RECALCUL TOTAL DE LUNIVERS")
                    drone.path = pathfinder.find_shortest_path(graph, drone.path[drone.path_index], graph.zones["zone_2"])


ARCHITECTURE A APPLIQUER 

while not all_arrived:

    # 1. chaque drone choisit sa prochaine case
    proposals = compute_moves()

    # 2. résolution des conflits
    valid_moves = resolve_conflicts(proposals)

    # 3. exécution
    apply_moves(valid_moves)

    # 4. drones bloqués
    update_waiting_times()

    # 5. éventuellement recalculer certains chemins
    reroute_stuck_drones()
