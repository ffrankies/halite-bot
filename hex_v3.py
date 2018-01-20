"""
Based on the Halite starter bot (Settler), and the "Improve Your Basic Bot" tutorial
found on the Halite website:
https://halite.io/learn-programming-challenge/downloads-and-starter-kits/improve-basic-bot
Version 3 of HEX
"""
import hlt # Halite engine
import logging
import time
import random

game = hlt.Game("HEX") # Init game

MAX_TIME = 2000 * 0.95

def planets_by_distance(ship):
    '''
    Creates a dictionary of all planets, where the keys are the distances 
    between the planets and the given ship.

    Based on nearby_entities_by_distance() in hlt/game_map.py
    '''
    result = {}
    for planet in game_map.all_planets():
        result[ship.calculate_distance_between(planet)] = planet
    return result
# End of planets_by_distance()

def timeout(start):
    '''
    If more than MAX_TIME elapsed since the start of turn, stop all calculations
    and send the current command queue to prevent triggering a timeout.

    Params:
    - start (int): The system clock value at the start of the current turn

    Returns:
    - timeout (bool): True if approaching timeout, False otherwise
    '''
    now = time.clock()
    elapsed = (now - start) * 1000
    if elapsed >= MAX_TIME:
        logging.info('Dodging timeout')
        return True
    return False
# End of timeout()

def select_target(ship):
    '''
    Selects a target to move towards.

    Params:
    - ship (hlt.entity.Ship): The ship looking for a target

    Return:
    - dock_target (hlt.entity.Planet): The planet to which to dock, 
            if possible. Defaults to None.
    - target (hlt.entity.Entity): The entity towards which to move,
            if not docking. Defaults to None.
    '''
    entities_by_distance = planets_by_distance(ship)
    distances = sorted(entities_by_distance)

    target = None
    dock_target = None
    for distance in distances:
        entity = entities_by_distance[distance]
        if not isinstance(entity, hlt.entity.Planet):
            continue # Next planet
        elif ship.can_dock(entity) and not entity.is_full():
            dock_target = entity # Dock if you can
            break
        elif entity.is_owned() and entity.owner.id == game_map.my_id:
            continue # Do not move towards planets I already own
        elif entity.is_owned(): # Not my planet
            target = random.choice(entity.all_docked_ships()) # Attack a docked ship
            break
        else: # Free planet
            target = entity
            break
    return dock_target, target
# End of select_target()

ship_targets = dict()
random.seed() # Seed with system time

while True:
    start = time.clock()
    # TURN START
    game_map = game.update_map() # Get latest version of map

    command_queue = [] # Sent to the engine at the end of turn
    for ship in game_map.get_me().all_ships():
        if ship.docking_status != ship.DockingStatus.UNDOCKED: # If ship is docked
            continue # Skip this ship
        
        # 50% chance of not changing targets
        if ship.id in ship_targets and random.random() > 0.5:
            logging.info('Moving to old target!')
            target = ship_targets[ship.id]
        else:
            logging.info('Moving to new target!')
            dock_target, target = select_target(ship)
        
        if (dock_target is None) and (target is None):
            # No free planets, all planets are mine
            logging.error('Both targets are None')
            continue # Next ship

        if timeout(start): break # Try to prevent timeout

        # Issuing command
        if dock_target is not None:
            # logging.info('Dock target: %s' % dock_target)
            command_queue.append(ship.dock(dock_target))
        else:
            ship_targets[ship.id] = target
            # logging.info('Target: %s' % target)
            navigate_command = ship.navigate(
                ship.closest_point_to(target),
                game_map,
                speed=hlt.constants.MAX_SPEED,
                ignore_ships=False)
            if navigate_command:
                command_queue.append(navigate_command)
        # End issuing command

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
