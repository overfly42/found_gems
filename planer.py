import numpy as np
from collections import deque, defaultdict
from itertools import permutations

from world import *
from analyser import *
from common import *

class PathPlanner:
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
        __self__.path_planner = PathPlanner(__self__.world)
        __self__.global_signal_analyzer = GlobalSignalAnalyzer(__self__.world)
        __self__.channel_signal_analyzer = ChannelSignalAnalyzer(__self__.world)
        __self__.antenna_signal_analyzer = AntennaSignalAnalyzer(__self__.world)
        __self__.planing_actions = {
            PLAN_COMPUTED:__self__.compute_selection,
            PLAN_GEMS:__self__.gem_selection,
            PLAN_OPPONENTS:__self__.not_implemented_yet,
            PLAN_PATROL:__self__.patrol_selection,
            PLAN_SIGNAL:__self__.not_implemented_yet,
            PLAN_UNKNOWN:__self__.exploration,
            PLAN_ANTENNA:__self__.antenna_placement
        }
        __self__.antenna_positions = [NW,SE,NE,NW]
        __self__.antenna_placed = {x:0 for x in __self__.antenna_positions}
        __self__.target_antenna_num = 0
    def new_tick(__self__):
        __self__.singal_memory.append({})
        __self__.channel_signal_analyzer.new_tick()
    def not_implemented_yet(__self__):
        log('This Plan is not implemented yet')

    def analyse_global_signal(__self__, signal_level: float):
        __self__.targets[PLAN_COMPUTED] = __self__.global_signal_analyzer.analyze(signal_level, __self__.signal_radius)
        if __self__.targets[PLAN_COMPUTED]:
            __self__.targets_changed = True

    def analyse_channel_signal(__self__, signals: list[float]):
        __self__.targets[PLAN_COMPUTED] = __self__.channel_signal_analyzer.analyze(signals, __self__.signal_radius)
        if __self__.targets[PLAN_COMPUTED]:
            __self__.targets_changed = True

    def analyse_antenna_signal(__self__, signals: list[dict]):
        __self__.antenna_signal_map = __self__.antenna_signal_analyzer.analyze(signals, __self__.signal_radius)
        log(f'Antenna signal map computed with shape {__self__.antenna_signal_map.shape}')

    def path_planing(__self__,start:tuple[int,int],target:tuple[int,int]) -> tuple[list[tuple[int,int]],int]:
        return __self__.path_planner.find_path(start, target)
    def exploration(__self__):
        fields = {(x,y) for x,y in np.argwhere(__self__.world.field == field_type.field.value)}
        if len(fields) == 0:
            return
        # walls = {(x,y) for x,y in np.argwhere(__self__.world.field == field_type.wall)}
        unseen = {(x,y) for x,y in np.argwhere(__self__.world.field == field_type.unknown.value)}
        targets = set()
        for u in unseen:
            for t in DIRS.values():
                new_target = (u[0]+t[0],u[1]+t[1])
                if new_target in fields:
                    targets.add(u)
        log(f'Number of Targets: {len(targets)}.')
        targets = sorted(targets,key=lambda x:euclidian_distance(__self__.world.bot_pos,x))
        __self__.targets[PLAN_UNKNOWN] = targets
    def gem_selection(__self__):
        if len(__self__.world.gems_seen) == 0:
            __self__.targets[PLAN_GEMS] = []
            return
        combinations = list(permutations(__self__.world.gems_seen))
        distance_score = []
        if len(combinations) < 10: #Actually this is up to 4 gems -> 24 combinations or 3 gems -> 6 combinations, but we want to be safe
            for i in range(len(combinations)):
                combo = [__self__.world.bot_pos]
                combo.extend(combinations[i])
                distance_score.append(0)
                for j in range(len(combo)-1):
                    distance_score[i] += __self__.path_planing(combo[j],combo[j+1])[1]
                log(f'Combo {combo} has length {distance_score[i]}')
            min_index = np.argmin(distance_score)
            __self__.targets[PLAN_GEMS] = combinations[min_index]
            log(f'Found {len(combinations)} gem combinations')
        else:
            log(f'Found {len(combinations)}: to long for computation, select nearest one.')
            closest = []
            for k,v in __self__.world.gems_seen.items():
                _,cost = __self__.path_planing(__self__.world.bot_pos,k)
                closest.append((v-cost,k))
            log(f'{closest}')
            closest.sort(key=lambda x: x[0],reverse=False)
            closest = [x[1] for x in closest]
            __self__.targets[PLAN_GEMS] = closest
            log(f'{closest}')            
    def antenna_placement(__self__):
        __self__.next_antenna = None
        max_placed_antenna = max(__self__.antenna_placed.values())
        next_antennas = [k for k,v in __self__.antenna_placed.items() if v < max_placed_antenna]
        antennas_left = __self__.target_antenna_num - sum(__self__.antenna_placed.values())
        if antennas_left <= 0:
            log('No antennas left to place.')
            __self__.targets[PLAN_ANTENNA] = []
            return
        if len(next_antennas) == 0:
            log('All antennas are placed equally, placing next one.')
            next_antennas = list(__self__.antenna_positions)
        if len(next_antennas) > antennas_left:
            log(f'More antennas to place than left, reducing options to {antennas_left}.')
            next_antennas = next_antennas[:antennas_left]
        distances = {k:euclidian_distance(__self__.world.bot_pos,__self__.world.antenna_positions[k]) for  k in next_antennas}
        next_antenna = min(distances,key=distances.get)
        log(f'Next antenna to place: {next_antenna} at distance {distances[next_antenna]}')
        __self__.targets[PLAN_ANTENNA] = [__self__.world.antenna_positions[next_antenna]]
        __self__.next_antenna = next_antenna

    def patrol_selection(__self__):
        '''
            This selects the next position to see a field, that is not for longest time.
        '''
        max_not_seen_value = max(__self__.world.fields_seen.values())
        relevant_fields = {k for k,v in __self__.world.fields_seen.items() if v == max_not_seen_value}
        log(f'Patrol Relevant Targets: {relevant_fields}')
        possible_targets = {k for k,v in __self__.world.visible_fields.items() if len(relevant_fields.intersection(v)) > 0}
        log(f'Patrol Possible Targets: {possible_targets}')
        possible_targets = sorted(possible_targets,key= lambda x:euclidian_distance(__self__.world.bot_pos,x))
        if len(possible_targets) > MAX_PATROL_TARGET:
            log(f'Reducing possible targets to {MAX_PATROL_TARGET}')
            possible_targets = possible_targets[:MAX_PATROL_TARGET]
        target_values =  {k:__self__.path_planing(__self__.world.bot_pos,k)[1] for k in possible_targets}
        __self__.targets[PLAN_PATROL] = list(k for k,v in sorted(target_values.items(),key=lambda item:item[1]))
        log(f'Patrol Fields: {__self__.targets[PLAN_PATROL]}')
    def compute_selection(__self__):
        i = None
        for i in range(len(__self__.targets.get(PLAN_COMPUTED,[]))):
            p,_ = __self__.path_planing(__self__.world.bot_pos,__self__.targets[PLAN_COMPUTED][i])
            if len(p) > 1:
                break
        if i != None:
            log(f'Removing the first {i} elements.')
            __self__.targets[PLAN_COMPUTED] = __self__.targets[PLAN_COMPUTED][i:]
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
            __self__.planing_actions[plan]()
            if plan in __self__.targets and len(__self__.targets[plan]) > 0:
                __self__.current_path,_ = __self__.path_planing(__self__.world.bot_pos,__self__.targets[plan][0])
                __self__.current_path = __self__.current_path[1:]
                if len(__self__.current_path) > 0:
                    break
    def analyse_multi_signal(__self__,signals:list):
        __self__.analyse_channel_signal(signals)
    def analyse_antenna_signal(__self__,signals:list):
        __self__.antenna_signal_map = __self__.antenna_signal_analyzer.analyze(signals, __self__.signal_radius)
        log(f'Antenna signal map computed with shape {__self__.antenna_signal_map.shape}')
                    
    def analyse_signal(__self__,singal_strength:float|list[float]):
        if isinstance(singal_strength,float):
            __self__.analyse_global_signal(singal_strength)
        elif isinstance(singal_strength,list):
            __self__.analyse_channel_signal(singal_strength)
        else:
            log(f'Could not handle singal of type {type(singal_strength)}, clean up and skip calculation')
            __self__.targets[PLAN_COMPUTED] = []
            __self__.first_signal = True
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
