from typing import Callable
from pydantic import ValidationError
from system import Graph, Connection, Zone, ZoneType
import sys


class Parser:
    """Parse un fichier de carte de drones."""

    def parse_file(self, filepath: str) -> Callable:
        """Charge et parse un fichier de carte."""
        graph = Graph()
        parse_dict = {}
        conn_list = []
        loc_a = None
        loc_b = None
        z = 0
        c = 0
        count_lines = 0
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
                count_lines += 1
        except FileNotFoundError:
            raise ValueError(f"Fichier introuvable : {filepath}")
        try:
            for i, line in enumerate(lines, start=1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    temp_dict = self.parse_line(line)
                    if "nb_drones" in temp_dict:
                        graph.nb_drones = temp_dict['nb_drones']
                    elif "zone_name" in temp_dict:
                        if any(x in temp_dict["zone_name"] for x in ("start", "goal")):
                            zone = Zone(
                                name=temp_dict["zone_name"],
                                x=temp_dict["x"],
                                y=temp_dict["y"],
                                max_drones=graph.nb_drones,
                            )
                        else:
                            zone = Zone(
                                name=temp_dict["zone_name"],
                                x=temp_dict["x"],
                                y=temp_dict["y"],
                            )
                        if zone.name == "start":
                            graph.start = zone
                        if zone.name == "goal":
                            graph.end = zone
                        if "zone" in temp_dict:
                            zone.zone_type = temp_dict["zone"]
                        if "color" in temp_dict:
                            zone.color = temp_dict["color"]
                            print(zone.color)
                        if "max_drones" in temp_dict:
                            zone.max_drones = int(temp_dict["max_drones"])
                        z += 1
                        parse_dict[f"{temp_dict['zone_name']}"] = zone
                    elif "loc_a" in temp_dict and "loc_b" in temp_dict:

                        loc_a = parse_dict.get(temp_dict["loc_a"])
                        loc_b = parse_dict.get(temp_dict["loc_b"])

                        if loc_a is None or loc_b is None:
                            raise Exception(
                                f"Wrong connection : {temp_dict['loc_a']} - {temp_dict['loc_b']}"
                            )

                        conn = Connection(
                            zone_a=loc_a,
                            zone_b=loc_b,
                        )

                        if "max_link_capacity" in temp_dict:
                            conn.max_link = int(temp_dict["max_link_capacity"])

                        if "current_usage" in temp_dict:
                            conn.current_usage = int(temp_dict["current_usage"])

                        conn_list.append(conn)

                        c += 1
                except Exception as e:
                    if isinstance(e, ValidationError):
                        for error in e.errors():
                            champ = error["loc"][0]
                            message = error["msg"]
                            fail_input = error["input"]
                            print(f"input {count_lines} : {champ}: {message}\n {fail_input} is not the good value.")
                    else:
                        print(e)
        except Exception as err:
            print(err)
            sys.exit()

        graph.zones = parse_dict
        graph.connections = conn_list

        return graph

    def parse_line(self, line: str) -> dict:
        if line.startswith("nb_drones"):
            key, value = line.split(":")
            drone_info = {
                "nb_drones": int(value)
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
                    elif vf == "normal":
                        zone_info[kf] = ZoneType.NORMAL
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
