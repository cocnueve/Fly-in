from __future__ import annotations
from typing import Any
from pydantic import ValidationError
from system import Graph, Connection, Zone, ZoneType
import sys


class Parser:
    """Parses a drone map file."""

    def parse_file(self, filepath: str) -> Graph:
        """Loads and parses a map file."""
        graph = Graph()
        parse_dict = {}
        conn_list = []
        seen_connections = set()
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
            raise ValueError(f"File not found: {filepath}")
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
                        is_hub_endpoint = temp_dict["kind"] in (
                            "start_hub", "end_hub"
                            )
                        if temp_dict["zone_name"] in parse_dict:
                            raise Exception(
                                f"duplicate zone: {temp_dict['zone_name']}"
                                )
                        if is_hub_endpoint:
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
                        if temp_dict["kind"] == "start_hub":
                            graph.start = zone
                        if temp_dict["kind"] == "end_hub":
                            graph.end = zone
                        if "zone" in temp_dict:
                            zone.zone_type = temp_dict["zone"]
                        if "color" in temp_dict:
                            zone.color = temp_dict["color"]
                        if "max_drones" in temp_dict and not is_hub_endpoint:
                            zone.max_drones = int(temp_dict["max_drones"])
                        z += 1
                        parse_dict[f"{temp_dict['zone_name']}"] = zone
                    elif "loc_a" in temp_dict and "loc_b" in temp_dict:

                        loc_a = parse_dict.get(temp_dict["loc_a"])
                        loc_b = parse_dict.get(temp_dict["loc_b"])

                        if loc_a is None or loc_b is None:
                            raise Exception(
                                f"Wrong connection : {temp_dict['loc_a']} "
                                f"- {temp_dict['loc_b']}"
                            )

                        pair = frozenset(
                            (temp_dict["loc_a"], temp_dict["loc_b"])
                            )
                        if pair in seen_connections:
                            raise Exception(
                                f"Duplicate connection: {temp_dict['loc_a']}"
                                f"-{temp_dict['loc_b']}"
                            )
                        seen_connections.add(pair)

                        conn = Connection(
                            zone_a=loc_a,
                            zone_b=loc_b,
                        )

                        if "max_link_capacity" in temp_dict:
                            conn.max_link = int(temp_dict["max_link_capacity"])

                        if "current_usage" in temp_dict:
                            conn.current_usage = int(
                                temp_dict["current_usage"]
                                )

                        conn_list.append(conn)

                        c += 1
                except Exception as e:
                    if isinstance(e, ValidationError):
                        details = []
                        for error in e.errors():
                            champ = error["loc"][0]
                            message = error["msg"]
                            fail_input = error["input"]
                            details.append(
                                f"{champ}: {message} "
                                f"({fail_input!r} is not the good value)"
                            )
                        raise ValueError(
                            f"line {i} ('{line}'): " + "; ".join(details)
                        ) from e
                    else:
                        raise ValueError(f"line {i} ('{line}'): {e}") from e
        except Exception as err:
            print(err)
            sys.exit()

        if graph.start is None:
            print("Error: no start_hub zone found in the file.")
            sys.exit()
        if graph.end is None:
            print("Error: no end_hub zone found in the file.")
            sys.exit()

        graph.zones = parse_dict
        graph.connections = conn_list

        return graph

    def parse_line(self, line: str) -> dict[str, Any]:
        if line.startswith("nb_drones"):
            key, value = line.split(":")
            drone_info = {
                "nb_drones": int(value)
            }
            return drone_info
        elif line.startswith(("start_hub", "end_hub", "hub")):
            kind, value = line.split(":")
            values = value.split()
            name, x, y, *feat = values
            zone_info: dict[str, Any] = {
                "kind": kind.strip(), "zone_name": name, "x": x, "y": y,
            }
            features = [f.strip("[]") for f in feat]
            for f in features:
                kf, vf = f.split("=")
                if kf == "zone":
                    if vf == "restricted":
                        zone_info[kf] = ZoneType.RESTRICTED
                    elif vf == "blocked":
                        zone_info[kf] = ZoneType.BLOCKED
                    elif vf == "priority":
                        zone_info[kf] = ZoneType.PRIORITY
                    elif vf == "normal":
                        zone_info[kf] = ZoneType.NORMAL
                    else:
                        raise Exception(f"invalid zone type: '{vf}'")
                elif kf in ["color", "max_drones"]:
                    zone_info[kf] = vf
            return zone_info

        elif line.startswith("connection"):
            key, value = line.split(":")
            connection_value = value.replace("-", " ")
            connection_values = connection_value.split()
            connection_values = [v.strip("[]") for v in connection_values]

            loc_a, loc_b, *conn_features = connection_values
            conn_info = {
                "loc_a": loc_a, "loc_b": loc_b,
            }
            for f in conn_features:
                key2, value2 = f.split("=")
                if key2 in ["max_link_capacity", "color", "max_drones"]:
                    conn_info[key2] = value2
            return conn_info

        else:
            return {}


if __name__ == "__main__":
    parser = Parser()
    parser.parse_file("/home/ffeder/Desktop/3e cercle/fly-in/config.txt")
    # parser.parse_line("connection: corridorA-goal [max_link_capacity=2]")
