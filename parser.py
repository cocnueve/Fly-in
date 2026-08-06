"""Parseur de fichiers de carte pour le simulateur Fly-in.

Un fichier de carte texte (voir dossier `maps/`) décrit, ligne par ligne :
- le nombre de drones à simuler (`nb_drones: ...`),
- les zones/hubs (`start_hub: ...`, `end_hub: ...`, `hub: ...`),
- les connexions entre zones (`connection: zoneA-zoneB [...]`).

Ce module transforme ce texte en un objet `Graph` exploitable par le
reste du programme (`fly-in.py`, `visualizer.py`).
"""

from __future__ import annotations
from typing import Any
from pydantic import ValidationError
from system import Graph, Connection, Zone, ZoneType
import sys


class Parser:
    """Parse un fichier de carte de drones."""

    def parse_file(self, filepath: str) -> Graph:
        """Charge et parse un fichier de carte.

        Lit le fichier ligne par ligne, ignore les lignes vides et les
        commentaires (`#`), puis délègue le parsing de chaque ligne
        utile à `parse_line`. Construit ensuite les zones et les
        connexions correspondantes et les assemble dans un `Graph`.

        Les erreurs de validation pydantic (valeurs hors bornes,
        champs manquants...) et les erreurs de connexion (zones
        inconnues) sont affichées sur la sortie standard plutôt que
        de faire planter tout le parsing : la ligne fautive est
        simplement ignorée et le parsing continue.

        Args:
            filepath: Chemin vers le fichier de carte à parser.

        Returns:
            Le graphe (`Graph`) construit à partir du fichier.

        Raises:
            ValueError: Si le fichier n'existe pas.
        """
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
                        is_start_or_goal = any(
                            x in temp_dict["zone_name"]
                            for x in ("start", "goal")
                        )
                        if is_start_or_goal:
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
                        if "max_drones" in temp_dict:
                            zone.max_drones = int(temp_dict["max_drones"])
                        z += 1
                        parse_dict[f"{temp_dict['zone_name']}"] = zone
                    elif "loc_a" in temp_dict and "loc_b" in temp_dict:

                        loc_a = parse_dict.get(temp_dict["loc_a"])
                        loc_b = parse_dict.get(temp_dict["loc_b"])

                        if loc_a is None or loc_b is None:
                            raise Exception(
                                f"Wrong connection : {temp_dict['loc_a']}"
                                f" - {temp_dict['loc_b']}"
                            )

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
                        for error in e.errors():
                            champ = error["loc"][0]
                            message = error["msg"]
                            fail_input = error["input"]
                            print(
                                f"input {count_lines} : {champ}: {message}\n"
                                f" {fail_input} is not the good value."
                            )
                    else:
                        print(e)
        except Exception as err:
            print(err)
            sys.exit()

        graph.zones = parse_dict
        graph.connections = conn_list

        return graph

    def parse_line(self, line: str) -> dict[str, Any]:
        """Parse une seule ligne du fichier de carte.

        Reconnaît trois formats de ligne : `nb_drones: N`, une zone
        (`start_hub:`, `end_hub:` ou `hub:`), ou une connexion
        (`connection:`). Les attributs entre crochets (ex:
        `[color=red max_drones=2]`) sont extraits sous forme de
        dictionnaire.

        Args:
            line: La ligne de texte à parser (déjà nettoyée des
                espaces superflus).

        Returns:
            Un dictionnaire décrivant l'élément trouvé sur la ligne
            (clé `nb_drones`, ou `zone_name`/`x`/`y`/..., ou
            `loc_a`/`loc_b`/...), ou un dictionnaire vide si la ligne
            ne correspond à aucun format reconnu.
        """
        if line.startswith("nb_drones"):
            key, value = line.split(":")
            drone_info = {
                "nb_drones": int(value)
            }
            return drone_info
        elif line.startswith(("start_hub", "end_hub", "hub")):
            key, value = line.split(":")
            values = value.split()
            name, x, y, *feat = values
            zone_info: dict[str, Any] = {
                "zone_name": name, "x": x, "y": y,
            }
            features = [f.strip("[]") for f in feat]
            for f in features:
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
