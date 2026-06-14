from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Callable
from pydantic import BaseModel, Field, model_validator


class ZoneType(Enum):
    NORMAL = "normal"       # coût 1 tour
    BLOCKED = "blocked"     # inaccessible
    RESTRICTED = "restricted"  # coût 2 tours
    PRIORITY = "priority"   # coût 1 tour, préféré

class Zone(BaseModel):
    name: str = Field(min_length=1, max_length=15)
    x: int = Field(ge=0, le=30)
    y: int = Field(ge=0, le=30)
    zone_type: Optional[ZoneType] = Field(default=ZoneType.NORMAL)
    color: Optional[str] = Field(default=None)
    max_drones: Optional[int] = Field(default=1, ge=0, le=10)
    current_drones: Optional[List["Drone"]] = Field(default_factory=list)  # drones présents ce tour
    waiting: Optional[int] = Field(default=0, ge=0, le=1000)
    temp_zone: Optional["Zone"] = Field(default=None)


    @model_validator(mode="after")
    def validator(self):
        if self.name == "hub" or self.name == "goal":
            self.max_drones = 5
        return self

    def is_accessible(self) -> int:
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
        if len(self.current_drones) >= self.max_drones:
            print(f"\nERROR: {self.name} got {len(self.current_drones)} for max {self.max_drones}")
            return False
        else:
            print(f"\nVALID: {self.name} got {len(self.current_drones)} for max {self.max_drones}")
            return True
    
    def add_drone(self, drone: Callable) -> int:
        if self.has_capacity():
            result = self.is_accessible()
            if result > 0:
                self.current_drones.append(drone)
                print(f"drone succesfuly moved from {drone.path[drone.path_index].name} to {self.name}")
                if self.has_capacity() is False:
                    self.temp_zone = self.zone_type
                    self.zone_type = ZoneType.BLOCKED

                return result
            else:
                return 0
        else:
            print(f"Zone not accessible.")
            return False

    def del_drone(self) -> bool:
        if len(self.current_drones) > 0:
            last_drones = self.current_drones.pop()
            print(f"VALID: D{last_drones.drone_id} has been deleted from {self.name}, {len(self.current_drones)} for max {self.max_drones}")
            if self.zone_type == ZoneType.BLOCKED:
                if self.temp_zone is not None:
                    self.zone_type = self.temp_zone
            self.waiting -= 1
            return True
        else:
            print(f"ERROR: Drone can't be deleted from {self.name}, {len(self.current_drones)} for max {self.max_drones}")
            return False


    
    def info(self) -> str:
        return(
            f"Name: {self.name}\nCoordinate: X={self.x}, Y={self.y}\
            \nZoneType: {self.zone_type}\nMax drone authorized: {self.max_drones}\
            \nCurrent drones: {len(self.current_drones)}"
        )

class Connection(BaseModel):
    zone_a : Zone
    zone_b : Zone
    max_link: Optional[int] = Field(default=1, ge=0, le=5)
    current_usage: Optional[int] = Field(default=0, ge=0, le=1)  # drones en transit ce tour

    @model_validator(mode="after")
    def check_all(self):
        if not self.has_capacity():
            raise ValueError("Too many drones in the area.")
        # print(f"\n CONNECTION '{self.zone_a.name} // {self.zone_b.name}' VALID READY FOR NEXT STEP")
        return self

    def has_capacity(self) -> bool:
        return self.current_usage <= self.max_link
    
    def change_usage(self, order: int) -> str:
        if order == 1:
            self.current_usage += 1
        elif order == 0:
            self.current_usage -= 1
        else:
            raise ValueError("put 0 or 1 when you use change_usage.")

class DroneState(Enum):
    WAITING = "waiting"
    MOVING = "moving"
    IN_TRANSIT = "in_transit"  # vers zone restricted
    ARRIVED = "arrived"

class Drone(BaseModel):
    drone_id: int = Field(ge=0, le=20)
    current_zone: Zone
    path: list[Zone]
    path_index: Optional[int] = Field(default=0, ge=0, le=1000)
    state: Optional[DroneState] = DroneState.WAITING
    transit_turns_remaining: Optional[int] = Field(default=0, ge=0, le=10)
    on_connection: Optional[Connection] = Field(default=None)

    def has_arrived(self) -> bool:
        return self.state == DroneState.ARRIVED
    
if __name__ == "__main__":
    from parser import Parser
    # hub_start = Zone(
    #     name="hub_start",
    #     x=0,
    #     y=0,
    #     zone_type="normal",
    #     max_drones=5,
    # )
    # place_a = Zone(
    #     name="place_a",
    #     x=1,
    #     y=0,
    #     zone_type="normal",
    #     max_drones=5,
    # )
    # corridor_up = Zone(
    #     name="corridor_up",
    #     x=2,
    #     y=1,
    #     zone_type="normal",
    #     max_drones=1,
    # )
    # corridor_down = Zone(
    #     name="corridor_down",
    #     x=2,
    #     y=0,
    #     zone_type="normal",
    #     max_drones=1,
    # )
    # hub_end = Zone(
    #     name="hub_end",
    #     x=3,
    #     y=0,
    #     zone_type="normal",
    #     max_drones=5,
    # )

    # start_to_place_a = Connection(
    #     start_zone=hub_start,
    #     zone_list=[place_a],
    #     max_link=1,
    #     current_usage=1,
    #     )
    # place_a_to_corr = Connection(
    #     start_zone=place_a,
    #     zone_list=[corridor_up, corridor_down],
    #     max_link=1,
    #     current_usage=1,
    #     )
    # corr_up_to_goal = Connection(
    #     start_zone=corridor_up,
    #     zone_list=[hub_end],
    #     max_link=1,
    #     current_usage=1,
    # )
    # corr_up_to_goal = Connection(
    #     start_zone=corridor_up,
    #     zone_list=[hub_end],
    #     max_link=1,
    #     current_usage=1,
    # )
    
