if "zone" in key:
    zone.zone_type = key
elif "color" in key:
    zone.color = key
elif "max_drones" in key:
    zone.max_drones = key

                if "max_link_capacity" in key:
                    conn.max_link = key
                elif "current_usage" in key:
                    conn.current_usage = key
