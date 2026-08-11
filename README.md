*This project has been created as part of the 42 curriculum by ffeder42.*

# Fly-in

## Description

Fly-in simulates a fleet of drones flying from a `start` zone to an `end`
zone through a network of interconnected zones, under movement and
capacity constraints:

- some zones cost more turns to enter (`restricted`), some are preferred
  (`priority`), some are completely inaccessible (`blocked`);
- zones and connections have a maximum simultaneous capacity;
- drones move simultaneously, turn by turn, and must wait or re-route
  when a path is congested.

The project is split into four object-oriented modules:

- `system.py` — the domain model: `Zone`, `Connection`, `Drone`, `Graph`.
- `parser.py` — turns a `.txt` map file into a `Graph`, validating the
  file format strictly (unique start/end zone, no duplicate zones or
  connections, valid zone types, capacity metadata ignored on
  start_hub/end_hub as required by the subject).
- `fly-in.py` — the pathfinder (`Pathfinder`, Dijkstra-based), the drone
  factory (`DroneFactory`), and the turn-by-turn simulation engine
  (`Simulation`).
- `visualizer.py` — a real-time Tkinter view of the simulation.

## Instructions

```bash
python fly-in.py <path_to_map_file>
```

The program reads the map file, computes an initial path with Dijkstra,
spawns `nb_drones` drones at the start zone, then runs the turn-by-turn
simulation until every drone reaches the end zone. Each turn, the
program prints a line listing every drone move for that turn, and a
Tkinter window shows the network and the drones live.

Dependency: `pydantic` (`pip install pydantic`).

## Algorithm choices & implementation strategy

- **Pathfinding**: Dijkstra's algorithm (`Pathfinder.find_shortest_path`),
  implemented from scratch with a binary heap (`heapq`) — no graph
  library is used. The edge cost is the movement cost of the destination
  zone; blocked zones are excluded from the search since
  `Zone.is_accessible()` returns 0 for them.
- **Restricted-zone transit**: entering a `restricted` zone takes 2
  turns. This is modeled with a dedicated `DroneState.IN_TRANSIT` state:
  on the first turn the drone leaves its zone and starts crossing the
  connection (its `path_index` is not advanced yet); on the second turn
  it completes the entry and `path_index` advances.
- **Restricted-zone capacity**: a restricted zone's capacity must not be
  exceeded even 2 turns ahead of time. Before a drone is allowed to
  start a transit, `Simulation.move_drone` counts not only the drones
  already inside the target zone, but also every drone currently in
  flight toward that same zone (`state == IN_TRANSIT` and
  `path[path_index + 1] == next_zone`), and refuses the move if the
  total would exceed `max_drones`. This keeps two drones from
  simultaneously committing to the same single-capacity restricted zone.
- **Congestion handling**: a drone that fails to move increments the
  `waiting` counter of its target zone. If more than 2 drones are queued
  for the same zone, the queued drones recompute a fresh shortest path
  from their current position (`Simulation.change_path`), re-routing
  around the bottleneck.
- **Complexity**: each Dijkstra run is `O((V + E) log V)`. It is only
  re-run for a drone when its queue actually gets congested, not every
  turn, which keeps the simulation practical even with many drones.

## Visual representation

`visualizer.py` opens a Tkinter window that redraws, every turn:

- every zone as a colored circle (color = the `color` metadata from the
  map file) with a live label showing `drones/max_drones` and the
  current waiting-queue size;
- every connection as a line labeled with its `max_link_capacity`;
- every drone as a small numbered circle positioned around the zone it
  currently occupies, colored by its state (`moving`, `waiting`,
  `arrived`).

This makes bottlenecks (a zone stuck at capacity, a growing queue)
immediately visible without reading the raw text output. Independently
of the graphical window, the simulation always prints the turn-by-turn
textual log required by the subject (see the example below).

## Example input and output

Input (`maps/medium/02_circular_loop.txt`, excerpt — `exit_point` is a
`restricted` zone with a default capacity of 1 drone):

```
nb_drones: 6

start_hub: start 0 0 [color=green]
hub: loop_a 1 0 [color=orange max_drones=2]
hub: loop_b 2 0 [color=orange max_drones=2]
hub: exit_point 3 0 [zone=restricted color=blue]
end_hub: goal 4 0 [color=red]

connection: start-loop_a [max_link_capacity=2]
connection: loop_a-loop_b [max_link_capacity=2]
connection: loop_b-exit_point
connection: exit_point-goal
```

Output (excerpt):

```
D1-loop_a D2-loop_a
D1-loop_b D2-loop_b D3-loop_a D4-loop_a
D1-loop_b-exit_point
D1-exit_point D3-loop_b D5-loop_a
D1-goal D2-loop_b-exit_point
...
```

`D1-loop_b-exit_point` shows drone 1 starting its 2-turn transit into
the restricted zone; `D1-exit_point` shows it arriving two turns later.
Drone 2 only starts its own transit once drone 1 has vacated the zone,
since `exit_point`'s capacity is 1.

## Resources

- [Pydantic documentation](https://docs.pydantic.dev/) — data validation
  used for the whole domain model.
- [Dijkstra's algorithm — Wikipedia](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
- [Python `heapq` documentation](https://docs.python.org/3/library/heapq.html)
- [Tkinter documentation](https://docs.python.org/3/library/tkinter.html)
- [mypy documentation](https://mypy.readthedocs.io/)
- [flake8 documentation](https://flake8.pycqa.org/)
