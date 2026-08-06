"""Modèles de données du simulateur Fly-in.

Ce module définit les objets métier manipulés par le reste du programme :
zones (`Zone`), connexions entre zones (`Connection`), drones (`Drone`)
et le graphe complet de la carte (`Graph`). Tous ces objets sont des
modèles pydantic, ce qui permet de valider automatiquement les valeurs
lues depuis le fichier de carte (coordonnées, capacités, etc.).
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class ZoneType(Enum):
    """Type d'une zone, qui détermine son accessibilité et son coût."""

    NORMAL = "normal"       # coût 1 tour
    BLOCKED = "blocked"     # inaccessible
    RESTRICTED = "restricted"  # coût 2 tours
    PRIORITY = "priority"   # coût 1 tour, préféré


class Zone(BaseModel):
    """Une zone (hub) de la carte, pouvant accueillir des drones.

    Attributes:
        name: Identifiant unique de la zone (ex: "start", "goal").
        x: Coordonnée X sur la carte.
        y: Coordonnée Y sur la carte.
        zone_type: Type de la zone (normal, bloqué, restreint, prioritaire).
        color: Couleur d'affichage (utilisée par le visualiseur).
        max_drones: Nombre maximum de drones pouvant occuper la zone
            en même temps.
        current_drones: Liste des drones actuellement présents sur
            la zone.
        waiting: Nombre de drones actuellement en attente d'entrer
            dans la zone.
        temp_zone: Sauvegarde du type de zone d'origine lorsque la zone
            est temporairement marquée BLOCKED (car pleine), afin de
            pouvoir le restaurer une fois qu'une place se libère.
        temp_drone: Champ réservé pour un usage futur (non utilisé
            actuellement par la logique de simulation).
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

    @model_validator(mode="after")
    def validator(self):
        """Point d'extension pydantic pour une validation croisée future."""
        return self

    def is_accessible(self) -> int | None:
        """Indique si la zone est traversable et avec quelle priorité.

        Returns:
            0 si la zone est bloquée (inaccessible), 1 si elle est
            restreinte, 2 si elle est normale, 3 si elle est prioritaire,
            ou None si le type de zone est inconnu.
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
        """Indique si la zone peut encore accueillir au moins un drone."""
        if self.current_drones is None:
            return False
        if self.max_drones is None:
            return False
        if len(self.current_drones) >= self.max_drones:
            return False
        else:
            return True

    def add_drone(self, drone: Drone) -> int:
        """Tente de faire entrer un drone dans la zone.

        Le comportement dépend à la fois de la capacité de la zone, de
        l'état de la connexion empruntée par le drone et du type de la
        zone (normal, restreint, prioritaire...).

        Args:
            drone: Le drone qui tente d'entrer dans la zone.

        Returns:
            Un code entier indiquant le résultat de la tentative :
            0/False si l'entrée est refusée, 1 si le drone entre en
            transit dans une zone restreinte, 2 ou 3 si le drone entre
            directement dans une zone normale ou prioritaire.
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
        """Retire un drone de la zone, si celui-ci s'y trouve.

        Si la zone était temporairement bloquée parce qu'elle était
        pleine, son type d'origine est restauré.

        Args:
            drone: Le drone à retirer de la zone.

        Returns:
            True si le drone a bien été retiré, False s'il n'était
            pas présent dans la zone.
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
        """Retourne une description lisible de l'état actuel de la zone."""
        return (
            f"Name: {self.name}\nCoordinate: X={self.x}, Y={self.y}\
            \nZoneType: {self.zone_type}\
            \nMax drone authorized: {self.max_drones}\
            \nCurrent drones: {len(self.current_drones)}"
        )


class Connection(BaseModel):
    """Une connexion (arête) entre deux zones du graphe.

    Attributes:
        zone_a: Une des deux zones reliées par la connexion.
        zone_b: L'autre zone reliée par la connexion.
        max_link: Nombre maximum de drones pouvant emprunter la
            connexion simultanément.
        current_usage: Nombre de drones actuellement en transit sur
            cette connexion, pendant le tour courant.
    """

    zone_a: Zone
    zone_b: Zone
    max_link: Optional[int] = Field(default=1, ge=0, le=5)
    # drones en transit ce tour
    current_usage: Optional[int] = Field(default=0, ge=0, le=5)

    @model_validator(mode="after")
    def check_all(self):
        """Vérifie, à la création, que la connexion n'est pas saturée."""
        if not self.conn_capacity():
            raise ValueError("Too many drones in the area.")
        return self

    def conn_capacity(self) -> bool:
        """Indique si la connexion peut encore accueillir un drone."""
        if self.max_link is None:
            return False
        if self.current_usage is None:
            return False
        if self.current_usage < self.max_link:
            return True
        else:
            return False

    def change_usage(self, order: int) -> None:
        """Met à jour le nombre de drones en transit sur la connexion.

        Args:
            order: 1 pour incrémenter l'usage courant d'un drone,
                0 pour réinitialiser l'usage à zéro (nouveau tour).
        """
        if self.current_usage is not None:
            if order == 1:
                self.current_usage += 1
            elif order == 0:
                self.current_usage = 0


class DroneState(Enum):
    """État courant d'un drone dans la simulation."""

    WAITING = "waiting"
    MOVING = "moving"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"


class Drone(BaseModel):
    """Un drone qui suit un chemin (`path`) d'une zone à une autre.

    Attributes:
        drone_id: Identifiant unique du drone.
        current_zone: Zone dans laquelle se trouve actuellement le drone.
        next_zone: Prochaine zone visée par le drone sur son chemin.
        path: Liste ordonnée des zones que le drone doit traverser,
            de la zone de départ jusqu'à la zone d'arrivée.
        path_index: Index de la zone courante du drone dans `path`.
        state: État courant du drone (en mouvement, en transit,
            arrivé...).
        remain: Compteur utilisé pour savoir si le drone est déjà
            comptabilisé dans la file d'attente d'une zone.
        on_connection: Connexion actuellement empruntée par le drone,
            le cas échéant.
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
        """Indique si le drone a atteint la fin de son chemin.

        Met également à jour `state` à `ARRIVED` si c'est le cas.

        Returns:
            True si le drone est arrivé au bout de `path`, False sinon.
        """
        if self.path_index is None:
            return False

        if self.path_index >= len(self.path) - 1:
            self.state = DroneState.ARRIVED
            return True
        else:
            return False

    def update_zone(self):
        """Met à jour `current_zone` et `next_zone` d'après `path_index`.

        Ne fait rien si le drone est déjà arrivé au bout de son chemin.

        Returns:
            Le drone lui-même (pour permettre le chaînage d'appels).
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
        """Cherche puis mémorise la connexion vers la prochaine zone.

        Args:
            graph: Le graphe contenant les zones et connexions.

        Returns:
            True si une connexion a été trouvée et assignée à
            `on_connection`, False sinon.
        """
        final_conn = self.update_conn(graph)
        if final_conn is None:
            return False
        else:
            self.on_connection = final_conn
            return True


class Graph(BaseModel):
    """Le graphe complet de la carte : zones, connexions et métadonnées.

    Attributes:
        zones: Dictionnaire associant le nom de chaque zone à l'objet
            `Zone` correspondant.
        connections: Liste de toutes les connexions entre zones.
        nb_drones: Nombre de drones à faire voler sur cette carte.
        start: Zone de départ de la simulation, si elle a été trouvée
            lors du parsing.
        end: Zone d'arrivée de la simulation, si elle a été trouvée
            lors du parsing.
    """

    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    nb_drones: int = Field(default=0, ge=0, le=50)
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
