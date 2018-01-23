"""
Weighted Bot
1. If ship is docked, leave it
2. Navigate to closest valuable entity
2b. Valuable defined as either enemy ship, unowned planet, or planet I own with few docked ships

Note: Please do not place print statements here as they are used to communicate with the Halite engine. If you need
to log anything use the logging module.
"""
import hlt
import logging
import time
import math
import collections

ENEMY_WORKERS = 0
ENEMY_WARRIORS =1
FRIENDLY_WARRIORS = 2
PLANETS = 3

class Grid:
    def __init__(self):
        self.planets = []
        self.workers = []
        self.warriors = []
        self.en_workers = []
        self.en_warriors = []

# GAME START
# Here we define the bot's name as Settler and initialize the game, including communication with the Halite engine.
game = hlt.Game("Grid Hero")
logging.info("Starting my closest entity bot!")
turn = 0
G_SIZE = 16
while True:
    turn += 1
    start_time = time.time()

    # TURN START
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()

    # Here we define the set of commands to be sent to the Halite engine at the end of the turn
    command_queue = []
    logging.info("TURN " + str(turn))
    me = game_map.get_me()
    total_ships = me.all_ships()
    planets = game_map.all_planets()
    my_ships = me.all_ships()

    start_time = time.time()
    #param type : int, None returns all, 0 for en_workers, 1 for en_warrior, 2 for warriors, 3 for planets,
    #return int : amount of entity specificied in surrounding grids
    def look_around(y, x, type, look_range):
        total = []
        for i in range(-(look_range) + 1, look_range):
            if (y + i) >= 0 and (y + i) < len(grid_map):
                grid_row = grid_map[y + i]
                for j in range(-(look_range) + 1, look_range):
                    if (x + j) >= 0 and (x + j) < len(grid_row):
                        if type == ENEMY_WORKERS:
                            total.extend(grid_row[x + j].en_workers)
                        elif type == ENEMY_WARRIORS:
                            total.extend(grid_row[x + j].en_warriors)
                        elif type == FRIENDLY_WARRIORS:
                            total.extend(grid_row[x + j].warriors)
                        elif type == PLANETS:
                            total.extend(grid_row[x + j].planets)
        return total

    def closest(ship, entities):
        result = None
        distance = 1000000
        for entity in entities:
            test_distance = ship.calculate_distance_between(entity)
            weight = 0
            if entity in planet_weights.keys():
                weight = planet_weights[entity]
            if (test_distance - weight) < distance:
                result = entity
                distance = test_distance - weight
        return result

    def navigate(ship, entity, ignore_ships=False, max_correction=90, angular_step=1):
        if type(entity) == hlt.entity.Planet and not entity.is_full() and (entity.owner == me or entity.owner == None) and ship.can_dock(entity):
            command_queue.append(ship.dock(entity))
            return True
        elif type(entity) == hlt.entity.Planet and entity.owner != me and entity.owner != None:
            return navigate(ship, closest(ship, entity.all_docked_ships()))
        else:
            if turn < 10:
                my_ships = 0
                if ship in my_warriors.keys():
                    my_ships = look_around(my_warriors[ship][0], my_warriors[ship][1], FRIENDLY_WARRIORS, 1)
                if len(my_ships) > 1:
                    speed=int(hlt.constants.MAX_SPEED * .5)
            else:
                speed=int(hlt.constants.MAX_SPEED)
            navigate_command = ship.navigate(
                ship.closest_point_to(entity),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=ignore_ships,
                max_corrections=max_correction,
                angular_step=angular_step)
            if navigate_command:
                command_queue.append(navigate_command)
                return True
            else:
                return False


    #Generate map Grid
    grid_map = []
    for i in range(0, game_map.height, G_SIZE):
        grid_row = []
        for j in range(0, game_map.width, G_SIZE):
            grid_row.append(Grid())
        grid_map.append(grid_row)

    #Add planets to grid
    workers = []
    planets_loc = {}
    for planet in planets:
        x = math.floor(planet.x / G_SIZE)
        y = math.floor(planet.y / G_SIZE)
        grid_map[y][x].planets.append(planet)
        planets_loc[planet] = (y, x)
        if planet.owner == me:
            grid_map[y][x].workers = planet.all_docked_ships()
            ships = planet.all_docked_ships()
            workers.extend(ships)
        elif planet.owner != None:
            grid_map[y][x].en_workers = planet.all_docked_ships()
            workers.extend(planet.all_docked_ships())


    warriors = []
    my_warriors = collections.OrderedDict()
    my_warr = []
    for player in game_map.all_players():
        for ship in player.all_ships():
            if ship in workers:
                continue
            warriors.append(ship)
            x = math.floor(ship.x / G_SIZE)
            y = math.floor(ship.y / G_SIZE)
            if player == me:
                my_warr.append(ship)
                my_warriors[ship] =  (y, x)
                if ship.docking_status == ship.DockingStatus.UNDOCKED:
                    grid_map[y][x].warriors.append(ship)
            else:
                grid_map[y][x].en_warriors.append(ship)


    planet_weights = {}
    targets = list(planets)
    for planet in planets:
        weight = 0
        x = planets_loc[planet][1]
        y = planets_loc[planet][0]
        work = look_around(y, x, ENEMY_WORKERS, 2)
        warr = look_around(y, x, ENEMY_WARRIORS, 2)
        friend_warr = look_around(y, x, FRIENDLY_WARRIORS, 2)
        close_warr = look_around(y, x, ENEMY_WARRIORS, 1)
        if planet.owner == None:
            weight += 5
            weight += (len(warr) * -5)
            if len(close_warr) > 0:
                weight += -5
                for ship in close_warr:
                    planet_weights[ship] = 15
                    targets.append(ship)
        elif planet.owner == me:
            weight += -10
            weight -= (((len(planet.all_docked_ships()) + 0) ** 2))
            if planet.is_full():
                weight += -10000000
            if len(warr) > 0:
                for ship in warr:
                    planet_weights[ship] = 10
                    targets.append(ship)
                for ship in close_warr:
                    if len(friend_warr) > len(close_warr):
                        planet_weights[ship] += (len(planet.all_docked_ships()) * 2)
                    else:
                        planet_weights[ship] += (len(planet.all_docked_ships()) * 5)
        else:
            if len(work) > 0:
                weight += 30 - (len(warr) * 15) - ((len(work) - 1) * 4)
            else:
                weight += (len(warr) * -5)

        #Is planet near the center
        x_center = math.fabs(x - (len(grid_map[y]) / 2))
        y_center = math.fabs(y - (len(grid_map) / 2))
        center = x_center + y_center
        center_weight = (len(grid_map) + len(grid_map[y])) / 4
        center = center_weight - center
        if center > 0:
            if len(game_map.all_players()) == 2:
                weight += (center * -2.5)
            else:
                weight += (center * -5)
        planet_weights[planet] = weight

    #Dists : List
    #Key : Target
    #Value : List of Lists, inner lists is distance and ship
    #[[[dist, ship0, target0], [dist, ship0, target1]], [[dist, ship1, target0], [dist, ship1, target1]]]
    dists = []
    for ship in my_warr:
        my_targets = list(targets)
        rogue = look_around(my_warriors[ship][0], my_warriors[ship][1], ENEMY_WARRIORS, 1)
        if len(rogue) > 0:
            my_targets = rogue
            for target in my_targets:
                planet_weights[target] = 5
        ship_dists = []
        for target in my_targets:
            ship_dists.append([ship.calculate_distance_between(target) - planet_weights[target], ship, target])
        ship_dists = sorted(ship_dists, key=lambda x: x[0])
        dists.append(ship_dists)
    dists = sorted(dists, key=lambda x: x[0][0])


    ship_commands = []
    #Iterate over sorted list, sending each ship
    #as long as either ship nor target has already been used
    while (len(dists) > 0):
        if time.time() - start_time > 1.3:
            break
        ship = dists.pop(0)
        target = ship[0][2]
        ship_commands.append((ship[0][1], target))
        weight = 0
        if type(target) == hlt.entity.Planet:
            if planet.owner == None:
                weight += -10
            elif planet.owner == me:
                weight += (-1 * (len(planet.all_docked_ships()) ** 2))
        else:
            weight += -20

        new_dists = []
        for ship_dists in dists:
            for ship in ship_dists:
                if ship[2] == target:
                    ship[0] -= weight
                    planet_weights[target] += weight
            ship_dists = sorted(ship_dists, key=lambda x: x[0])
            new_dists.append(ship_dists)
        new_dists = sorted(new_dists, key=lambda x: x[0][0])
        dists = new_dists

    for command in ship_commands:
        if time.time() - start_time > 1.8:
            break
        navigate(command[0], command[1])

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
