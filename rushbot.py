"""
Based on the Halite starter bot (Settler), and the "Improve Your Basic Bot" tutorial
found on the Halite website:
https://halite.io/learn-programming-challenge/downloads-and-starter-kits/improve-basic-bot
"""
import hlt # Halite engine
import logging

game = hlt.Game("Rusher") # Init game
logging.info("Starting Rusher bot!")

while True:
    # TURN START
    game_map = game.update_map() # Get latest version of map

    command_queue = [] # Sent to the engine at the end of turn
    for ship in game_map.get_me().all_ships():
        if ship.docking_status != ship.DockingStatus.UNDOCKED: # If ship is docked
            continue # Skip this ship

        entities_by_distance = game_map.nearby_entities_by_distance(ship)
        f = filter(lambda e: isinstance(e[1][0], hlt.entity.Planet), entities_by_distance.items())
        planets_by_distance = list(f)
        closest_planets = sorted(planets_by_distance, key=lambda tup: tup[0])
        closest_planets = [tup[1][0] for tup in closest_planets]

        for planet in closest_planets:
            logging.info('Chosen planet: %s' % planet)
            if ship.can_dock(planet) and not planet.is_full():
                logging.info('Docking ship')
                command_queue.append(ship.dock(planet)) # Dock to nearest unowned planet if possible
            else:
                if planet.is_owned() and planet.owner.id == game_map.my_id:
                    continue
                logging.info('Moving ship to closest planet')
                navigate_command = ship.navigate(
                    ship.closest_point_to(planet),
                    game_map,
                    speed=int(hlt.constants.MAX_SPEED/2),
                    ignore_ships=False)
                if navigate_command:
                    command_queue.append(navigate_command)
            break

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
