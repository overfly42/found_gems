import numpy as np
from collections import deque, defaultdict
from itertools import permutations
import random

random.seed(1)

from world import *
from analyser import *
from common import *

class PathPlannerAStar:
    def __init__(self, world: World):
        self.world = world

    def find_path(self, start: tuple[int, int], target: tuple[int, int]) -> tuple[list[tuple[int, int]], int]:
        f = self.world.field
        q = deque()
        q.append((0, start))
        current_path = {}
        score = defaultdict(lambda: float('inf'))
        score[start] = 0

        while q:
            _, current = q.popleft()
            if target == current:
                break
            for dx, dy in DIRS.values():
                nxt = (current[0] + dx, current[1] + dy)
                if nxt == target:
                    current_path[nxt] = current
                    q.clear()
                    q.append((0, nxt))
                    break
                x, y = nxt
                if x < 0 or x >= self.world.height or y < 0 or y >= self.world.width:
                    continue
                if f[x, y] == field_type.wall.value:
                    continue
                tentative_score = score[current] + f[x, y]
                if tentative_score < score[nxt]:
                    current_path[nxt] = current
                    score[nxt] = tentative_score
                    q.append((tentative_score, nxt))

        if target not in current_path:
            return [], float('inf')

        actual_path = [target]
        while target in current_path:
            target = current_path[target]
            actual_path.append(target)
        actual_path.reverse()
        final_score = max([v for k, v in score.items() if k in actual_path])
        return actual_path, final_score

class Planer:
    def __init__(__self__,world:World):
        __self__.world = world
        __self__.targets_changed = True
        __self__.first_signal = True
        __self__.signal_radius = 0.0
        __self__.targets = {
            PLAN_COMPUTED: [],
            PLAN_GEMS: [],
            PLAN_OPPONENTS: [],
            PLAN_PATROL: [],
            PLAN_SIGNAL: [],
            PLAN_UNKNOWN: [],
            PLAN_ANTENNA: []
        }
        __self__.computed_not_in_counter = 0
        __self__.gems_computed:set[tuple[int,int]] = set()
        __self__.singal_memory = []
        __self__.current_path:list[tuple[int,int]] = []
        __self__.signal_map = np.zeros_like(__self__.world.field)
        __self__.path_planner = PathPlannerAStar(__self__.world)
        __self__.plan_computed = PlanComputed(world, __self__.path_planner, __self__)
        __self__.plan_gems = PlanGems(world, __self__.path_planner, __self__)
        __self__.plan_unknown = PlanUnknown(world, __self__.path_planner, __self__)
        __self__.plan_antenna = PlanAntenna(world, __self__.path_planner)
        __self__.plan_patrol = PlanPatrol(world, __self__.path_planner, __self__)
        __self__.plan_not_implemented = PlanNotImplemented(world, __self__.path_planner, __self__)
        __self__.analyzer = MultiSourceAnalyzer(__self__.world)        
        __self__.planing_actions = {
            PLAN_COMPUTED: __self__.plan_computed.plan,
            PLAN_GEMS: __self__.plan_gems.plan,
            PLAN_OPPONENTS: __self__.plan_not_implemented.plan,
            PLAN_PATROL: __self__.plan_patrol.plan,
            PLAN_SIGNAL: __self__.plan_not_implemented.plan,
            PLAN_UNKNOWN: __self__.plan_unknown.plan,
            PLAN_ANTENNA: __self__.plan_antenna.plan
        }
    def new_tick(__self__):
        __self__.singal_memory.append({})
        __self__.analyzer.new_tick()
    def update(__self__):
        __self__.plan_antenna.update()
    def analyse(__self__,data:dict):
        __self__.new_tick()
        __self__.targets[PLAN_COMPUTED] = __self__.analyzer.analyze(data)
        current_target = None if not __self__.current_path else __self__.current_path[-1]
        if __self__.targets[PLAN_COMPUTED] and current_target not in __self__.targets[PLAN_COMPUTED]:
            __self__.targets_changed = True
            current_target = __self__.world.bot_pos if current_target is None else current_target
#            __self__.targets[PLAN_COMPUTED].sort(key=lambda x: euclidian_distance(current_target, x))
            __self__.targets[PLAN_COMPUTED].sort(key=lambda x: euclidian_distance(__self__.world.bot_pos, x))
        __self__.plan_global()


    def plan_global(__self__):
        if __self__.current_path and not (__self__.world.world_changed or __self__.targets_changed):
            log('Use existing path')
            return
        log(f'Current path: {__self__.current_path}')
        log(f'World changed: {__self__.world.world_changed}, targets changed: {__self__.targets_changed}')
        __self__.targets_changed = False
        __self__.world.world_changed = False
        log('Calculating new Path')
        plan_order = [
            PLAN_GEMS,
            PLAN_ANTENNA,
            PLAN_COMPUTED,
            PLAN_UNKNOWN,
            PLAN_SIGNAL,
            PLAN_PATROL,
        ]
        #Update the global plan
        __self__.current_path = []
        for plan in plan_order:
            log(f'Using {plan}')
            targets = __self__.planing_actions[plan]()
            if targets != None:
                __self__.targets[plan] = targets
            if plan in __self__.targets and len(__self__.targets[plan]) > 0:
                __self__.current_path,_ = __self__.path_planner.find_path(__self__.world.bot_pos,__self__.targets[plan][0])
                __self__.current_path = __self__.current_path[1:]
                if len(__self__.current_path) > 0:
                    break

    def signal_level_to_distance(__self__,signal_level:float)->float:
        # Distance formula
        # s = 1 / (1 + (d/r)²)
        # With d = distance, r = __self__.signal_radius, s = signal_level
        # Distance is given without any borders
        # s = 1 / (1 + (d/r)²)  solve for d
        # s * (1 + (d/r)²) = 1
        # 1 + (d/r)² = 1/s
        # (d/r)² = (1/s) - 1
        # d/r = sqrt((1/s) - 1)
        # d = r * sqrt((1/s) - 1)
        # d = r * sqrt((1 - s)/s)

        if signal_level > 1:
#            log(f'Invalid signal level {signal_level}, returning inf distance',log_level.ERROR)
#            return float('inf')
            log(f'Singal level {signal_level} greater than 1, using half of Singal')
            signal_level = 1.0
        if signal_level <= 0:
            log(f'Signal level is 0, returning inf distance',log_level.INFO)
            return float('inf')
        distance = __self__.signal_radius * ((1 - signal_level)/signal_level)**0.5
        return distance
    def gaussian_distance_ring(__self__,robot_pos, target_distance, sigma, amplitude=1.0) -> np.ndarray:
        """
        Creates a Gaussian ring around a robot position.

        Parameters
        ----------
        robot_pos : (row, col)
            Robot position.
        target_distance : float
            Distance where the signal is strongest.
        sigma : float
            Thickness of the ring.
        amplitude : float
            Peak value.

        Returns
        -------
        grid : np.ndarray
            2D array with Gaussian ring.
        """

        rows = __self__.world.height
        cols = __self__.world.width
        ry, rx = robot_pos

        # Coordinate grid
        y, x = np.ogrid[:rows, :cols]

        # Distance from robot
        dist = np.sqrt((x - rx)**2 + (y - ry)**2)

        # Gaussian centered on the distance d0
        grid = amplitude * np.exp(-(dist - target_distance)**2 / (2 * sigma**2))

        return grid
    def get_next_move(__self__)->str:
        antenna_move = __self__.plan_antenna.get_antenna_move(__self__.world.bot_pos, __self__.current_path)
        if antenna_move:
            return antenna_move
        elif __self__.current_path:
            log(f'Path length: {len(__self__.current_path)}')
            next_pos = __self__.current_path[0]
            del __self__.current_path[0]
            log(f'next_pos: {next_pos}')
            log(f'bot_pos: {__self__.world.bot_pos}')
            direction =(next_pos[0]-__self__.world.bot_pos[0],next_pos[1]-__self__.world.bot_pos[1])
            log(f'selected direction: {direction}')
            move = DIRS_INV[direction]
        else:
            move = random.choice(list(DIRS.keys()))
            __self__.current_path.clear()
        if move == 'WAIT':
            __self__.current_path.clear()
        return move
    def highlight_targets(__self__)->str:
        if LOG_LEVEL == log_level.GAME:
            return ''
        maps = {}
        highlight = []
        if PLAN_UNKNOWN in __self__.targets and __self__.targets[PLAN_UNKNOWN]:
            for pos in __self__.targets[PLAN_UNKNOWN]:
                highlight.append([int(pos[1]),int(pos[0]),'#FFFFFF'])
        for pos in __self__.current_path:
            highlight.append([int(pos[1]),int(pos[0]),'#F00000'])
        if PLAN_COMPUTED in __self__.targets and __self__.targets[PLAN_COMPUTED]:
            for pos in __self__.targets[PLAN_COMPUTED]:
                highlight.append([int(pos[1]),int(pos[0]),'#00FF00'])
            y,x = __self__.targets[PLAN_COMPUTED][0]
            highlight.append([int(x),int(y),'#991199'])
        maps['highlight'] = highlight
        return maps

class PlanBasic:
    def __init__(__self__,world:World,path_planner:PathPlannerAStar,planer=None):
        __self__.world = world
        __self__.path_planner:PathPlannerAStar = path_planner
        __self__.planer = planer
    def plan(__self__) -> list[tuple[int,int]]:
        raise NotImplementedError()

class PlanComputed(PlanBasic):
    def plan(__self__):
        targets = list(__self__.planer.targets.get(PLAN_COMPUTED, []))
        for index, target in enumerate(targets):
            path, _ = __self__.path_planner.find_path(__self__.world.bot_pos, target)
            if len(path) > 1:
                return targets[index:]
        return []

class PlanGems(PlanBasic):
    def plan(__self__):
        if len(__self__.world.gems_seen) == 0:
            return []

        combinations = list(permutations(__self__.world.gems_seen))
        if len(combinations) < 10:
            distance_score = []
            for combo in combinations:
                path_combo = [__self__.world.bot_pos] + list(combo)
                score = 0
                for src, dst in zip(path_combo, path_combo[1:]):
                    score += __self__.path_planner.find_path(src, dst)[1]
                distance_score.append(score)
                log(f'Combo {path_combo} has length {score}')
            min_index = np.argmin(distance_score)
            return list(combinations[min_index])

        log(f'Found {len(combinations)}: to long for computation, select nearest one.')
        closest = []
        for position, value in __self__.world.gems_seen.items():
            _, cost = __self__.path_planner.find_path(__self__.world.bot_pos, position)
            closest.append((value - cost, position))
        closest.sort(key=lambda x: x[0])
        return [position for _, position in closest]

class PlanUnknown(PlanBasic):
    def plan(__self__):
        fields = {(x, y) for x, y in np.argwhere(__self__.world.field == field_type.field.value)}
        if len(fields) == 0:
            return []

        unseen = {(x, y) for x, y in np.argwhere(__self__.world.field == field_type.unknown.value)}
        targets = set()
        for u in unseen:
            for t in DIRS.values():
                new_target = (u[0] + t[0], u[1] + t[1])
                if new_target in fields:
                    targets.add(u)
        log(f'Number of Targets: {len(targets)}.')
        return sorted(targets, key=lambda x: euclidian_distance(__self__.world.bot_pos, x))

class PlanAntenna(PlanBasic):
    def __init__(__self__, world: World, path_planner: PathPlannerAStar):
        __self__.world = world
        __self__.path_planner = path_planner
        __self__.antenna_positions = {}
        __self__.antenna_placed = {}
        __self__.target_antenna_num = 0
        __self__.next_antenna = None
        __self__.last_direction = None

    def update(__self__):
        __self__.antenna_positions = {NW: (__self__.world.mid_height//2,__self__.world.mid_width//2),
                                      SE: ((3*__self__.world.mid_height)//2,(3*__self__.world.mid_width)//2),
                                      NE: (__self__.world.mid_height//2,(3*__self__.world.mid_width)//2),
                                      SW: ((3*__self__.world.mid_height)//2,__self__.world.mid_width//2)}
        __self__.antenna_placed = {x: 0 for x in __self__.antenna_positions}

    def set_target_antenna_count(__self__, count: int):
        __self__.target_antenna_num = count

    def plan(__self__):
        __self__.next_antenna = None
        max_placed_antenna = max(__self__.antenna_placed.values())
        next_antennas = [k for k, v in __self__.antenna_placed.items() if v < max_placed_antenna]
        antennas_left = __self__.target_antenna_num - sum(__self__.antenna_placed.values())
        if antennas_left <= 0:
            log('No antennas left to place.')
            return []
        log('Updating Antenna Positions')
        for k,v in __self__.antenna_positions.items():
            if __self__.world.field[v] == field_type.field.value:
                log(f'Antenna {k} at position {v} is on a field, recalculating.')
                near_walls = [tuple(x) for x in np.argwhere(__self__.world.field == field_type.wall.value)]
                near_walls = sorted(near_walls, key=lambda x: euclidian_distance(v, x))
                if near_walls:
                    __self__.antenna_positions[k] = near_walls[0]
                    log(f'New position for antenna {k} is {__self__.antenna_positions[k]}')
#            log(f'Antenna {k} at position {v} has been placed {__self__.antenna_placed[k]} times.')
        if len(next_antennas) == 0:
            log('All antennas are placed equally, placing next one.')
            next_antennas = list(__self__.antenna_positions)
        if len(next_antennas) > antennas_left:
            log(f'More antennas to place than left, reducing options to {antennas_left}.')
            next_antennas = next_antennas[:antennas_left]
        distances = {k: euclidian_distance(__self__.world.bot_pos, __self__.antenna_positions[k]) for k in next_antennas}
        next_antenna = min(distances, key=distances.get)
        log(f'Next antenna to place: {next_antenna} at distance {distances[next_antenna]}')
        __self__.next_antenna = next_antenna
        return [__self__.antenna_positions[next_antenna]]

    def get_antenna_move(__self__, bot_pos: tuple[int, int], current_path: list) -> str:
        log(f'Current path for next antenna: {__self__.next_antenna} in {len(current_path)} steps.')
        if __self__.next_antenna is None:# or len(current_path) > 5:
            return None
        if not current_path:
            return None
        dist = euclidian_distance(bot_pos, __self__.antenna_positions[__self__.next_antenna])
        if dist > 5.0:
            return None
        log(f'Moving towards antenna {__self__.next_antenna} at position {__self__.antenna_positions[__self__.next_antenna]}')
        #Check if next move is valid (no wall)
        for d in DIRS.values():
            neighbor = tuple(np.array(bot_pos) + np.array(d))
            if 0 <= neighbor[0] < __self__.world.height and 0 <= neighbor[1] < __self__.world.width:
                if __self__.world.field[neighbor] == field_type.wall.value:
                    log(f'Neighbor {neighbor} is a wall, placing antenna there.')
                    __self__.antenna_placed[__self__.next_antenna] += 1
                    __self__.next_antenna = None
                    return f'PA{DIRS_INV[tuple(d)]}'
        # next_field_coord = current_path[0] if current_path else None
        # if next_field_coord is None:
        #     return None
        # next_field_type = __self__.world.field[next_field_coord]
        # log(f'Next field type: {field_type(next_field_type).name} at {next_field_coord}')
        # if next_field_type != field_type.wall.value:
        #     return None
        # direction = np.array(next_field_coord) - np.array(bot_pos)
        # direction = tuple(np.sign(direction))
        # if direction in DIRS_INV:
        #     __self__.antenna_placed[__self__.next_antenna] += 1
        #     __self__.next_antenna = None
        #     return f'PA{DIRS_INV[tuple(direction)]}'
        return None

    def get_last_antenna_direction(__self__):
        return __self__.last_direction

class PlanNotImplemented(PlanBasic):
    def plan(__self__):
        log('This plan is not implemented yet')
        return []

class PlanPatrol(PlanBasic):
    def plan(__self__):
        '''
            This selects the next position to see a field, that is not for longest time.
        '''
        max_not_seen_value = max(__self__.world.fields_seen.values())
        relevant_fields = {k for k, v in __self__.world.fields_seen.items() if v == max_not_seen_value}
        log(f'Patrol Relevant Targets: {relevant_fields}')
        possible_targets = {k for k, v in __self__.world.visible_fields.items() if len(relevant_fields.intersection(v)) > 0}
        log(f'Patrol Possible Targets: {possible_targets}')
        possible_targets = sorted(possible_targets, key=lambda x: euclidian_distance(__self__.world.bot_pos, x))
        if len(possible_targets) > MAX_PATROL_TARGET:
            log(f'Reducing possible targets to {MAX_PATROL_TARGET}')
            possible_targets = possible_targets[:MAX_PATROL_TARGET]
        target_values = {k: __self__.path_planner.find_path(__self__.world.bot_pos, k)[1] for k in possible_targets}
        targets = [k for k, v in sorted(target_values.items(), key=lambda item: item[1])]
        log(f'Patrol Fields: {targets}')
        return targets
