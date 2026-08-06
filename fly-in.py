"""Point d'entrée du simulateur Fly-in.

Ce script charge une carte, calcule un premier chemin optimal du
départ vers l'arrivée avec l'algorithme de Dijkstra (`Pathfinder`),
crée les drones puis fait tourner la boucle de simulation tour par
tour en affichant le résultat via `Visualizer`.
"""

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
    """Nœud de la file de priorité utilisée par l'algorithme de Dijkstra.

    Attributes:
        cost: Coût cumulé du chemin menant à cette zone (utilisé
            pour l'ordre dans le tas).
        zone: Zone représentée par ce nœud.
        path: Chemin complet (liste de zones) menant du départ à
            cette zone.
    """

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
        """Retourne le chemin de coût minimal, ou None si impossible.

        Implémente l'algorithme de Dijkstra à l'aide d'un tas
        (`heapq`) : à chaque étape, on explore la zone non visitée
        de coût cumulé minimal, jusqu'à atteindre `end`.

        Args:
            graph: Le graphe dans lequel chercher un chemin.
            start: La zone de départ.
            end: La zone d'arrivée visée.

        Returns:
            La liste ordonnée des zones à traverser (départ inclus,
            arrivée incluse), ou None si aucun chemin n'existe.
        """
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
            return 3
        elif zone.zone_type == ZoneType.BLOCKED:
            return 4
        elif zone.zone_type == ZoneType.PRIORITY:
            return 1
        else:
            return 2


class DroneFactory():
    """Fabrique de drones, positionnés sur une zone de départ."""

    def __init__(self):
        pass

    def create_drone(self, id: int, start_zone: Zone, path: list[Zone]):
        """Crée un nouveau drone placé sur `start_zone` avec son chemin.

        Args:
            id: Identifiant à donner au drone.
            start_zone: Zone de départ du drone.
            path: Chemin complet que le drone doit suivre.

        Returns:
            Le `Drone` nouvellement créé.
        """
        return Drone(drone_id=id, current_zone=start_zone, path=path)


def move_drone(drone: Drone, graph: Graph) -> bool:
    """Fait avancer un drone d'une zone vers la suivante si possible.

    Args:
        drone: Le drone à déplacer.
        graph: Le graphe contenant les zones et connexions.

    Returns:
        True si le drone a effectivement avancé d'une zone, False sinon
        (connexion pleine, zone suivante pleine, drone déjà en transit...).
    """
    # path_index est théoriquement toujours un int une fois le drone créé
    # (valeur par défaut 0). On le rend explicite pour mypy et pour la
    # robustesse : un drone sans path_index ne peut pas être déplacé.
    assert drone.path_index is not None

    # verif qu'il existe une zone precedante.
    if drone.path[drone.path_index] is not None:
        if drone.path_index < len(drone.path) - 1:
            current_zone = drone.path[drone.path_index]  # zone precedante.
            next_zone = drone.path[drone.path_index + 1]
            if drone.check_conn(graph) is True:
                # check_conn() n'est True que lorsqu'il a réussi à assigner
                # une connexion réelle au drone.
                assert drone.on_connection is not None
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


def change_path(drone: Drone) -> bool:
    """Recalcule le plus court chemin du drone vers l'arrivée du graphe.

    Args:
        drone: Le drone dont on veut recalculer le trajet.

    Returns:
        True si un nouveau chemin a été trouvé (et assigné au drone),
        False si aucun chemin n'existe ou si le graphe/drone est mal formé.
    """
    assert drone.path_index is not None
    if graph.end is None:
        return False
    new_path = pathfinder.find_shortest_path(
        graph, drone.path[drone.path_index], graph.end
    )
    if new_path is not None:
        drone.path = new_path
        return True
    else:
        return False


if __name__ == "__main__":
    # set-up program
    try:
        parser = Parser()
        pathfinder = Pathfinder()
        graph = parser.parse_file(
            "/home/ffeder/Desktop/3e cercle/Fly-in/config.txt"
        )

        # start/end sont Optional côté modèle (tant qu'aucune zone "start" /
        # "goal" n'a été rencontrée dans le fichier). On vérifie ici une
        # bonne fois pour toutes que la carte est valide avant de continuer.
        if graph.start is None or graph.end is None:
            raise ValueError(
                "La carte ne définit pas de zone 'start' et/ou 'goal'."
            )
        start_zone = graph.start
        end_zone = graph.end

        pathfinded = pathfinder.find_shortest_path(graph, start_zone, end_zone)
        if pathfinded is None:
            raise ValueError("Aucun chemin trouvé entre 'start' et 'goal'.")

        fact = DroneFactory()
        drone_list = []
    except Exception:
        raise

    vis = Visualizer(graph)
    TOUR_DELAY = 0.7  # seconds between tours, so you can watch it happen

    # drone factory
    for i in range(graph.nb_drones):
        temp_drone = fact.create_drone(i + 1, start_zone, pathfinded)
        drone_list.append(temp_drone)

    # drone set-up
    for drone in drone_list:
        start_zone.add_drone(drone)

    i = 0
    # algo
    while any(drone.state != DroneState.ARRIVED for drone in drone_list):
        i += 1
        if i > 50:  # safety for dodge overflow.
            print(
                "The program has been automaticly close, it overpassed"
                " the 50 tries."
            )
            sys.exit()
        for drone in drone_list:
            # set connection pointed by the drone to 0.
            if drone.on_connection is not None:
                drone.on_connection.change_usage(0)
            if drone.state == DroneState.ARRIVED:
                continue

            if drone.path_index < len(drone.path) - 1:
                drone.update_zone()  # update target zones of the drone.
                # deplace le drone et renvoie si ca a marche ou non.
                result = move_drone(drone, graph)

                if result is False:
                    # Si le drone n'est pas en attente, il entre dans la file.
                    if drone.remain < 1:
                        drone.next_zone.waiting += 1
                        drone.remain += 1

                    # Si la file de la zone depasse la limite, elle
                    # recalcule un chemin.
                    if drone.next_zone.waiting > 2:
                        change_path(drone)
                        # Si la drone est en attente, il sort de la file.
                        if drone.remain > 0:
                            drone.remain -= 1
                            drone.next_zone.waiting -= 1
                # Si le drone est passe alors qu'il etait dans la queue,
                # il en sort.
                elif (
                    result is True
                    and drone.next_zone.waiting > 0
                    and drone.remain > 0
                ):
                    drone.remain -= 1
                    drone.next_zone.waiting -= 1
            else:
                # Si le drone est arrivee au bout du path, il change
                # de drone_state.
                drone.state = DroneState.ARRIVED

        vis.update(drone_list, i)
        time.sleep(TOUR_DELAY)

    vis.update(drone_list, i)
    print("\nAll drones arrived. Close the visualizer window to exit.")
    vis.wait_until_closed()
