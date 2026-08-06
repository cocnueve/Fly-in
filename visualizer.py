"""Visualisation Tkinter en temps réel de la simulation Fly-in.

Ce module dessine la carte (zones et connexions) sur un canvas Tkinter
et rafraîchit à chaque tour la position des drones, leur état
(couleur) et les informations d'occupation/file d'attente de chaque
zone.
"""

import tkinter as tk
import math


# =========================
# CONFIGURATION VISUELLE
# =========================

ZONE_COLORS = {
    "blue": "#4a90d9",
    "red": "#d62d06",
    "orange": "#e08b00",
    "green": "#1fa34a",
    "yellow": "#d6c600",
    "gray": "#666666",
    "cyan": "#00bcd4",
    "lime": "#14c400",
    "brown": "#523c00",
    "purple": "#8702a8",
    "gold": "#f2ff00",
    "magenta": "#d452ff",
}

DRONE_COLORS = {
    "MOVING": "#2ecc71",
    "WAITING": "#f39c12",
    "ARRIVED": "#3498db",
    "DEFAULT": "#e63946",
}


ZONE_RADIUS = 32
DRONE_RADIUS = 10

BACKGROUND = "#fafafa"


class Visualizer:
    """
    Visualiseur temps réel de la simulation Fly-in.

    Fonctionnalités :
    - adaptation automatique à la taille de la carte
    - zoom automatique
    - hubs lisibles
    - drones autour des zones
    - affichage des files d'attente
    """

    def __init__(self, graph, width=1920, height=1080):
        """Construit la fenêtre et dessine la carte statique initiale.

        Args:
            graph: Le graphe (`Graph`) à afficher.
            width: Largeur de la fenêtre/canvas, en pixels.
            height: Hauteur de la fenêtre/canvas, en pixels.
        """

        self.graph = graph
        self.closed = False

        self.width = width
        self.height = height

        self.root = tk.Tk()
        self.root.title("Fly-in - Drone Simulation")
        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._on_close
        )

        self.status = tk.StringVar()
        self.status.set("Tour 0")

        label = tk.Label(
            self.root,
            textvariable=self.status,
            font=("Consolas", 13, "bold")
        )
        label.pack(pady=5)

        self.canvas = tk.Canvas(
            self.root,
            width=width,
            height=height,
            bg=BACKGROUND
        )

        self.canvas.pack()
        self.zone_pos = {}
        self.zone_items = {}
        self.zone_text = {}
        self.drone_items = []
        self.scale = 1
        self._calculate_scale()
        self._compute_positions()
        self._draw_connections()
        self._draw_zones()
        self._draw_legend()

    def _calculate_scale(self):
        """Calcule le facteur de zoom et le décalage pour centrer la carte.

        Détermine `self.scale`, `self.offset_x` et `self.offset_y` de
        façon à ce que toutes les zones du graphe tiennent dans le
        canvas, avec une marge, quelle que soit l'étendue de la carte.
        """

        zones = list(self.graph.zones.values())

        if not zones:
            self.scale = 50
            self.offset_x = 0
            self.offset_y = 0
            return

        min_x = min(z.x for z in zones)
        max_x = max(z.x for z in zones)
        min_y = min(z.y for z in zones)
        max_y = max(z.y for z in zones)

        width = max(max_x - min_x, 1)
        height = max(max_y - min_y, 1)
        margin = 150

        sx = (self.width - 2 * margin) / width
        sy = (self.height - 2 * margin) / height

        self.scale = min(sx, sy)
        # centre du monde
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        # translation vers le centre de la fenêtre
        self.offset_x = self.width / 2 - center_x * self.scale
        self.offset_y = self.height / 2 - center_y * self.scale

    def _compute_positions(self):
        """Convertit les coordonnées (x, y) de chaque zone en pixels."""

        for name, zone in self.graph.zones.items():
            x = zone.x * self.scale + self.offset_x
            y = zone.y * self.scale + self.offset_y
            self.zone_pos[name] = (x, y)

    def _draw_connections(self):
        """Dessine toutes les connexions (lignes) entre zones."""

        for conn in self.graph.connections:
            x1, y1 = self.zone_pos[
                conn.zone_a.name
            ]
            x2, y2 = self.zone_pos[
                conn.zone_b.name
            ]
            self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill="#999999",
                width=3
            )

            # capacité du lien
            if hasattr(conn, "max_link"):
                mx = (x1 + x2) / 2
                my = (y1 + y2) / 2

                self.canvas.create_text(
                    mx,
                    my,
                    text=str(conn.max_link),
                    font=("Consolas", 9, "bold"),
                    fill="#555555"
                )

    def _draw_zones(self):
        """Dessine chaque zone (cercle coloré + texte d'info dessous)."""

        for name, zone in self.graph.zones.items():
            x, y = self.zone_pos[name]
            color = ZONE_COLORS.get(
                str(zone.color),
                "#4a90d9"
            )
            circle = self.canvas.create_oval(
                x - ZONE_RADIUS,
                y - ZONE_RADIUS,
                x + ZONE_RADIUS,
                y + ZONE_RADIUS,
                fill=color,
                outline="black",
                width=2
            )
            info = self.canvas.create_text(
                x,
                y + ZONE_RADIUS + 20,
                text=self._zone_info(zone),
                font=("Consolas", 6),
                fill="#333333"
            )
            self.zone_items[name] = circle
            self.zone_text[name] = info

    @staticmethod
    def _zone_info(zone):
        """Retourne le texte affiché sous une zone (occupation, file)."""
        return (
            f"Drones : {len(zone.current_drones)}/{zone.max_drones}\n"
            f"Waiting : {zone.waiting}"
        )

    def _refresh_zones(self):
        """Met à jour le texte d'info affiché sous chaque zone."""
        for name, zone in self.graph.zones.items():
            if name in self.zone_text:
                self.canvas.itemconfig(
                    self.zone_text[name],
                    text=self._zone_info(zone)
                )

    def _clear_drones(self):
        """Supprime du canvas tous les dessins de drones du tour précédent."""
        for item in self.drone_items:
            self.canvas.delete(item)
        self.drone_items = []

    def _drone_color(self, drone):
        """Retourne la couleur d'affichage associée à l'état du drone."""
        state = str(
            getattr(
                drone,
                "state",
                ""
            )
        )

        for key in DRONE_COLORS:
            if key in state:
                return DRONE_COLORS[key]
        return DRONE_COLORS["DEFAULT"]

    def _draw_drones(self, drone_list):
        """Dessine tous les drones, répartis en cercle autour de leur zone.

        Args:
            drone_list: Liste de tous les drones de la simulation.
        """
        self._clear_drones()
        grouped = {}
        for drone in drone_list:
            if drone.path is None:
                continue
            zone = drone.path[
                drone.path_index
            ]
            grouped.setdefault(
                zone.name,
                []
            ).append(drone)

        for zone_name, drones in grouped.items():
            if zone_name not in self.zone_pos:
                continue
            cx, cy = self.zone_pos[
                zone_name
            ]
            count = len(drones)
            # drones autour du hub
            radius = ZONE_RADIUS + 35 + len(drones)
            for i, drone in enumerate(drones):
                angle = (
                    2
                    * math.pi
                    * i
                    / max(count, 1)
                )
                dx = (
                    cx
                    + radius
                    * math.cos(angle)
                )
                dy = (
                    cy
                    + radius
                    * math.sin(angle)
                )
                color = self._drone_color(
                    drone
                )
                circle = self.canvas.create_oval(
                    dx - DRONE_RADIUS,
                    dy - DRONE_RADIUS,
                    dx + DRONE_RADIUS,
                    dy + DRONE_RADIUS,
                    fill=color,
                    outline="black"
                )
                text = self.canvas.create_text(
                    dx,
                    dy,
                    text=str(
                        drone.drone_id
                    ),
                    font=("Consolas", 8, "bold")
                )
                self.drone_items.extend(
                    [
                        circle,
                        text
                    ]
                )

    def _draw_legend(self):
        """Dessine la légende des couleurs en haut à droite de la fenêtre."""
        x = self.width - 150
        y = 80
        self.canvas.create_text(
            x,
            y - 30,
            text="LEGEND",
            font=("Consolas", 12, "bold")
        )
        colors = [
            ("normal", "#4a90d9"),
            ("restricted", "#d62d06"),
            ("priority", "#00bcd4"),
            ("drone", "#e63946")
        ]
        for i, (name, color) in enumerate(colors):
            yy = y + i * 30
            self.canvas.create_oval(
                x - 60,
                yy - 8,
                x - 45,
                yy + 8,
                fill=color,
                outline="black"
            )
            self.canvas.create_text(
                x,
                yy,
                text=name,
                anchor="w",
                font=("Consolas", 9)
            )

    def update(self, drone_list, tour):
        """Rafraîchit l'affichage pour le tour courant de la simulation.

        Ne fait rien si la fenêtre a déjà été fermée par l'utilisateur.

        Args:
            drone_list: Liste de tous les drones de la simulation.
            tour: Numéro du tour courant, affiché dans le titre.
        """
        if self.closed:
            return

        self._refresh_zones()
        self._draw_drones(
            drone_list
        )
        self.status.set(
            f"Tour {tour}   |   drones : {len(drone_list)}"
        )
        self.root.update()

    def _on_close(self):
        """Callback appelé à la fermeture de la fenêtre par l'utilisateur."""
        self.closed = True
        self.root.destroy()

    def wait_until_closed(self):
        """Bloque le programme jusqu'à la fermeture de la fenêtre."""

        if not self.closed:
            self.root.mainloop()
