import hlt
import logging
import time
import math
from enum import Enum

"""
The Halite map is a two-dimensional plane of width x and height y
to increase look up speeds, it will be broken up into a two-dimensional
array of Grid Objects. grid_map[0][0] will represent the grid in the top
left position of the map, grid_map[0] being the first row of grids along the
top of the map.

Ships currently docked on planets cannot attack back without first taking
several turns to undock, because of this docked shops are classified as
workers and undocked are warriors in the context of this bot.
"""

class Map:
    me = None

    class Grid:
        def __init__(self):
            # Entities within the boundries of the grid
            self.planets = [] # All planets
            self.workers = [] # My workers
            self.warriors = [] # My warriors
            self.enemy_workers = []
            self.enemy_warriors = []

    class EntityType(Enum):
        ENEMY_WORKERS = 0
        ENEMY_WARRIORS = 1
        FRIENDLY_WARRIORS = 2
        PLANETS = 3

    def __init__(self, game_map):
        # G_SIZE is the width and height of the grids of the map
        # Lower values would give a higher resolution grid of the map but
        # at the expensive of valuable compute time
        self.G_SIZE = 16

        # Two-dimensional array of Grid Objects representing the map state
        self.grid_map = []

        # Dictionary of all entities with value being a tuple of (y, x) grid
        # index for instant lookups
        self.entity_position = {}

        # List of all of my ships not docked on a planet
        self.warriors = []

        # List of all 'valuable' planets and ships and their weights
        # See _initialize_target_weights() for more information
        self.target_weights = {}

        # Three-dimensional array of all warrior-target pairs and distance
        # See _init_ship_to_target() for more information
        self.distances = []

        self._initialize_grid(game_map)
        self._populate_grid(game_map)
        self._initialize_target_weights(game_map)
        self._init_ship_to_target()

    # Param : Game map from halite engine
    # Return : None
    # Creates the two-dimensional array of Grids based on map size
    def _initialize_grid(self, game_map):
        for i in range(0, game_map.height, self.G_SIZE):
            grid_row = []
            for j in range(0, game_map.width, self.G_SIZE):
                grid_row.append(self.Grid())
            self.grid_map.append(grid_row)


    # Param : Game map from halite engine
    # Return : None
    # Adds all planets and ships to the grid map
    def _populate_grid(self, game_map):
        me = game_map.get_me()
        Map.me = me

        # Add planets to grid
        for planet in game_map.all_planets():
            x = math.floor(planet.x / self.G_SIZE)
            y = math.floor(planet.y /self.G_SIZE)
            self.grid_map[y][x].planets.append(planet)
            self.entity_position[planet] = (y, x)
            if planet.owner == me:
                self.grid_map[y][x].workers = planet.all_docked_ships()
            elif planet.owner != None:
                self.grid_map[y][x].enemy_workers = planet.all_docked_ships()

        # Add ships to grid
        for player in game_map.all_players():
            for ship in player.all_ships():
                if ship.docking_status == ship.DockingStatus.DOCKED:
                    continue
                x = math.floor(ship.x / self.G_SIZE)
                y = math.floor(ship.y / self.G_SIZE)
                if player == me:
                    self.warriors.append(ship)
                    self.entity_position[ship] =  (y, x)
                    self.grid_map[y][x].warriors.append(ship)
                else:
                    self.grid_map[y][x].enemy_warriors.append(ship)

    """
    Self.target_weights is a dictonary with keys of any potential targets and
    values of their weights. Weights are considered at a 1:1 ratio with  the
    absolute ( or real) distance to the target.

    Example: A ship considering two targets. Target1 is 50 distance away with
    a weight of +10. Target2 is 30 distance away with a weight of -15. Weights are
    subtracted from absolute distance to find the relative distance. Target1 then
    has a relative distance of 40, and target2 a relative distance of 45. The ship
    will consider target1 closer and navigate towards that entity.

    Current weights are rough estimates based on observation and testing of
    200-300 games and be middle ground between aggressiveness and passiveness
    for the highest halite leaderboard rating with this type of bot.
    """
    # Param : Game map from halite engine
    # Return : None
    def _initialize_target_weights(self, game_map):
        # Adjust weights to change how the bot prioritizes targets
        # Higher weights increase likelihood of a ship choosing target

        # Planet Weights
        EMPTY_PLANET = 5
        MY_PLANET = -10
        EN_WARRIORS = -5
        CLOSE_EN_WARRIORS = -5 # Added to ENEMY_WARRIOR weight
        CENTER = -5 # Only applied in 4 player matches
        def PRODUCTION(planet): # Subtracts weight based on ships I already docked
            return -1 * ((len(planet.all_docked_ships()) + 0) ** 2)
        def EN_PLANET_STR(planet, work, warr): # Determines strength of enemy planet
            return 30 - (len(warr) * 15) + ((len(work) - 1) * 4)

        # Ship weights
        BLOCKING_SHIPS = EMPTY_PLANET  * 1.5 # Enemy ships close to a free planet
        ATTACKING_SHIPS = EMPTY_PLANET * 2 # Enemy ships attacking a planet I own

        planets = game_map.all_planets()
        targets = list(planets)
        for planet in planets:
            weight = 0
            x = self.entity_position[planet][1]
            y = self.entity_position[planet][0]
            en_work = self.look_around(y, x, Map.EntityType.ENEMY_WORKERS, 2)
            en_warr = self.look_around(y, x, Map.EntityType.ENEMY_WARRIORS, 2)
            #friend_warr = self.look_around(y, x, Map.EntityType.FRIENDLY_WARRIORS, 2)
            close_en_warr = self.look_around(y, x, Map.EntityType.ENEMY_WARRIORS, 1)

            if planet.owner == None:
                weight += EMPTY_PLANET
                weight += (len(en_warr) * EN_WARRIORS)
                if len(close_en_warr) > 0:
                    weight += CLOSE_EN_WARRIORS
                    for ship in close_en_warr:
                        # Add enemy ships close to planets to potential targets
                        self.target_weights[ship] = BLOCKING_SHIPS
            elif planet.owner == Map.me:
                if planet.is_full():
                    # Do not consider
                    continue

                weight += MY_PLANET
                weight += PRODUCTION(planet)
                for ship in en_warr:
                    self.target_weights[ship] = ATTACKING_SHIPS
            else:
                weight += EN_PLANET_STR(planet, en_work, en_warr)

            #In 4 player matches, check if planet is near the center
            if len(game_map.all_players()) == 4:
                x_center = math.fabs(x - (len(self.grid_map[y]) / 2))
                y_center = math.fabs(y - (len(self.grid_map) / 2))
                center = x_center + y_center
                center_weight = (len(self.grid_map) + len(self.grid_map[y])) / 4
                center = center_weight - center
                if center > 0:
                    weight += (center * CENTER)

            self.target_weights[planet] = weight

    # Param : y and x are grid positions, not coordinates on the map
    # Param : type is enum of entity type
    # Param : Look_range is int of grid range to search, 1 checks only your grid
    # while 2 would search all grids 1 away from you
    # Return type : list  of entities specificied in surrounding grid range
    def look_around(self, y, x, type, look_range):
        total = []
        for i in range(-(look_range) + 1, look_range):
            if (y + i) >= 0 and (y + i) < len(self.grid_map):
                grid_row = self.grid_map[y + i]
                for j in range(-(look_range) + 1, look_range):
                    if (x + j) >= 0 and (x + j) < len(grid_row):
                        if type == Map.EntityType.ENEMY_WORKERS:
                            total.extend(grid_row[x + j].enemy_workers)
                        elif type == Map.EntityType.ENEMY_WARRIORS:
                            total.extend(grid_row[x + j].enemy_warriors)
                        elif type == Map.EntityType.FRIENDLY_WARRIORS:
                            total.extend(grid_row[x + j].warriors)
                        elif type == Map.EntityType.PLANETS:
                            total.extend(grid_row[x + j].planets)
        return total


    # Creates the master list of ship-target pairs
    # self.distances is three-dimensional array
    # [[[dist, ship0, target0], [dist, ship0, target1]], [[dist, ship1, target0], [dist, ship1, target1]]]
    # Finds the ship closest to its closest target
    def _init_ship_to_target(self):
        for ship in self.warriors:
            my_targets = list(self.target_weights.keys())

            #Check for rogue enemy ships near current position
            rogue = self.look_around(self.entity_position[ship][0], self.entity_position[ship][1], Map.EntityType.ENEMY_WARRIORS, 1)
            if len(rogue) > 0:
                my_targets = rogue
                for target in my_targets:
                    self.target_weights[target] = 5

            ship_dists = []
            for target in my_targets:
                ship_dists.append([ship.calculate_distance_between(target) - self.target_weights[target], ship, target])
            ship_dists = sorted(ship_dists, key=lambda x: x[0])
            self.distances.append(ship_dists)
        self.distances = sorted(self.distances, key=lambda x: x[0][0])

    # Param: Target and weight to update
    # Return: None
    # Updates master list of distances and re-sorts
    def _update_ship_to_target(self, target, weight):
        self.target_weights[target] += weight
        new_dists = []
        for ship_dists in self.distances:
            for ship in ship_dists:
                if ship[2] == target:
                    ship[0] -= weight
            ship_dists = sorted(ship_dists, key=lambda x: x[0])
            new_dists.append(ship_dists)
        new_dists = sorted(new_dists, key=lambda x: x[0][0])
        self.distances = new_dists

    # Return: Ship, Target tuple of the 'best' or highest weighted move for
    # the given map state
    def next_move(self):
        if len(self.distances) == 0:
            return None
        move = self.distances.pop(0)
        ship = move[0][1]
        target = move[0][2]

        # Update weights for certain actions
        weight = 0
        if type(target) == hlt.entity.Planet:
            if target.owner == None:
                weight += -10
            elif target.owner == Map.me:
                weight += -1 * ((len(target.all_docked_ships()) + 1) ** 1.25)
        else:
            weight += -10

        self._update_ship_to_target(target, weight)
        return (ship, target)

# Param: Ship, list of entities
# Return: Closest entity to the ship
# Rarely used, doesn't consider weights or other ships may be closer
def closest(ship, entities):
    result = None
    distance = 1000000
    for entity in entities:
        test_distance = ship.calculate_distance_between(entity)
        if test_distance < distance:
            result = entity
            distance = test_distance
    return result

# Param: Ship to send, entity to go towards
# Returns: Halite string for command queue
# Will correctly handle docking on the planet when it approaches, or
# destroying enemy workers stationed on the planet before docking
def navigate(ship, entity, ignore_ships=False, max_correction=90, angular_step=1):
    if type(entity) == hlt.entity.Planet:
        # If the ship can dock at planet, dock
        if (entity.owner == Map.me or entity.owner == None) and ship.can_dock(entity) and not entity.is_full():
             return ship.dock(entity)
        # If there are enemies on the planet, target the closest ship
        elif entity.owner != Map.me and entity.owner != None:
            return navigate(ship, closest(ship, entity.all_docked_ships()))
    return ship.navigate(
        ship.closest_point_to(entity),
        game_map,
        speed=int(hlt.constants.MAX_SPEED),
        ignore_ships=ignore_ships,
        max_corrections=max_correction,
        angular_step=angular_step)


# GAME START
game = hlt.Game("Grid Hero")

#Turn counter
turn = 0
while True:
    # TURN START
    turn += 1
    logging.info("TURN " + str(turn))
    start_time = time.time()
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()

    # Commands to be sent at end of turn
    command_queue = []

    turn_map = Map(game_map)

    # Get the highest rated move from the map until there are none left
    move = turn_map.next_move()
    while (move != None):
        # Exit loop if out of time and send commands generated so far
        # This bot generates moves from most important to least so time outs
        # are not critical
        if time.time() - start_time > 1.8:
            break
        command = navigate(move[0], move[1])
        if command:
            command_queue.append(command)
        move = turn_map.next_move()

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
