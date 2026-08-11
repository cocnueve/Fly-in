"""Real-time Tkinter visualisation of the Fly-in simulation.

This module draws the map (zones and connections) on a Tkinter canvas 
and refreshes the position of the drones, their state (colour) and 
the occupancy/queue information of each zone at each turn.
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
    Real-time viewer for the Fly-in simulation.

    Features:
    - automatic adjustment to map size
    - automatic zoom
    - visible hubs
    - drones around zones
    - queue display
    """

    def __init__(self, graph, width=1920, height=1080):
        """Creates the window and draws the initial static map.

        Args:
            graph: The graph (`Graph`) to display.
            width: Width of the window/canvas, in pixels.
            height: Height of the window/canvas, in pixels.
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
        """Calculates the zoom factor and the offset to center the map.

        Determines `self.scale`, `self.offset_x`, and `self.offset_y`
        so that all areas of the graph fit within the
        canvas, with a margin, regardless of the map's extent.
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
        """Converts the (x, y) coordinates of each area to pixels."""

        for name, zone in self.graph.zones.items():
            x = zone.x * self.scale + self.offset_x
            y = zone.y * self.scale + self.offset_y
            self.zone_pos[name] = (x, y)

    def _draw_connections(self):
        """Draw all the connections (lines) between zones."""

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
        """Draw each area (colored circle + info text below it)."""

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
        """Returns the text displayed below a field (occupation, queue)."""
        return (
            f"Drones : {len(zone.current_drones)}/{zone.max_drones}\n"
            f"Waiting : {zone.waiting}"
        )

    def _refresh_zones(self):
        """Updates the tooltip text displayed below each field."""
        for name, zone in self.graph.zones.items():
            if name in self.zone_text:
                self.canvas.itemconfig(
                    self.zone_text[name],
                    text=self._zone_info(zone)
                )

    def _clear_drones(self):
        """Removes all drone drawings from the previous turn from the canvas."""
        for item in self.drone_items:
            self.canvas.delete(item)
        self.drone_items = []

    def _drone_color(self, drone):
        """Returns the display color associated with the drone's status."""
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
        """Draw all the drones, arranged in a circle around their area.

        Args:
            drone_list: List of all drones in the simulation.
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
        """Draw the color key in the upper-right corner of the window."""
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
        """Refreshes the display for the current lap of the simulation.

        Does nothing if the window has already been closed by the user.

        Args:
            drone_list: List of all drones in the simulation.
            lap: Number of the current lap, displayed in the title.
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
        """A callback function called when the user closes the window."""
        self.closed = True
        self.root.destroy()

    def wait_until_closed(self):
        """Pauses the program until the window is closed."""

        if not self.closed:
            self.root.mainloop()
