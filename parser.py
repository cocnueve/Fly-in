import re
from typing import Optional, Callable
from graph import Graph

class Parser:
    """Parse un fichier de carte de drones."""

    def parse_file(self, filepath: str) -> Callable:
        from zone import Zone, Connection
        """Charge et parse un fichier de carte."""
        graph = Graph()
        parse_dict = {}
        conn_list = []
        loc_a = None
        loc_b = None
        z = 0
        c = 0
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise ValueError(f"Fichier introuvable : {filepath}")

        for i, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                temp_dict = self.parse_line(line)
                if "zone_name" in temp_dict:
                    zone = Zone(
                        name=temp_dict["zone_name"],
                        x=temp_dict["x"],
                        y=temp_dict["y"],
                    )
                    if "zone" in temp_dict:
                        zone.zone_type = temp_dict["zone"]
                    elif "color" in temp_dict:
                        zone.color = temp_dict["color"]
                    elif "max_drones" in temp_dict:
                        zone.max_drones = temp_dict["max_drones"]
                    z += 1
                    parse_dict[f"zone_{z}"] = zone

                elif "loc_a" in temp_dict and "loc_b" in temp_dict:
                    for z in parse_dict.values():
                        if temp_dict["loc_a"] == z.name:
                            loc_a = z
                        elif temp_dict["loc_b"] == z.name:
                            loc_b = z
                        if loc_a is not None and loc_b is not None:
                            # print(f"loc_a: {loc_a}")
                            # print(f"loc b: {loc_b}")
                            conn = Connection(
                                zone_a=loc_a,
                                zone_b=loc_b,
                            )

                            if "max_link_capacity" in temp_dict:
                                conn.max_link = temp_dict["max_link_capacity"]

                            if "current_usage" in temp_dict:
                                conn.current_usage = temp_dict["current_usage"]
                            loc_a = None
                            loc_b = None
                            conn_list.append(conn)

                    c += 1
            except ValueError as e:
                raise ValueError(f"Ligne {i} : {e}")

        graph.zones = parse_dict
        graph.connections = conn_list
        return graph
    
    def parse_line(self, line: str) -> dict:
        from zone import ZoneType
        parse_dict = {}
        if line.startswith("nb_drones"):
            key, value = line.split(":")
            drone_info = {
                "drone_nb": value
            }
            return drone_info
        elif line.startswith(("start_hub", "end_hub", "hub")):
            key, value = line.split(":")
            value = value.split()
            name, x, y, *feat = value
            zone_info = {
                "zone_name": name, "x": x, "y": y,
            }
            feat = [f.strip("[]") for f in feat]
            for f in feat:
                kf, vf = f.split("=")
                if kf in ["zone", "color", "max_drones"]:
                    if vf == "restricted":
                        zone_info[kf] = ZoneType.RESTRICTED
                    elif vf == "blocked":
                        zone_info[kf] = ZoneType.BLOCKED
                    elif vf == "priority":
                        zone_info[kf] = ZoneType.PRIORITY
                    else:
                        zone_info[kf] = vf
                return zone_info
            
        elif line.startswith("connection"):
            key, value = line.split(":")
            value = value.replace("-", " ")
            value = value.split()
            value = [v.strip('[]') for v in value]
            loc_a, loc_b, *feat = value
            conn_info = {
                "loc_a": loc_a, "loc_b": loc_b,
            }
            for f in feat:
                key2, value2 = f.split("=")
                if key2 in ["max_link_capacity", "color", "max_drones"]:
                    conn_info[key2] = value2
            return conn_info


if __name__ == "__main__":
    parser = Parser()
    parser.parse_file("/home/ffeder/Desktop/3e cercle/fly-in/config.txt")
    # parser.parse_line("connection: corridorA-goal [max_link_capacity=2]")
