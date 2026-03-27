import json
import sys
import random
import os
import numpy as np

from enum import Enum
from collections import defaultdict, deque
from itertools import permutations

random.seed(1)

#region global variables
DIRS = {
    'W': (0, -1),
    'E': (0, 1),
    'N': (-1, 0),
    'S': (1, 0),
}
DIRS_INV = defaultdict(lambda : str('WAIT'))
for k,v in DIRS.items():
    DIRS_INV[v] = k
#region singal handling
#GAUS_RING_INTERVALS = [3.0, 2.5, 2.0, 1.5, 1.0]#, 0.75, 0.66, 0.5, 0.33, 0.25]
GAUS_RING_INTERVALS = [1.0, 0.75, 0.66, 0.5, 0.33, 0.25]
# GAUS_RING_INTERVALS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
SIGMA = 1.5
SIGNAL_MAP_DECAY = 0.9
SIGNAL_THRESHHOLD = 0.5
COPUTE_THREASHOLD = 0.75
NUM_SIGNAL_OCCOURENCES = 2
#endregion
MAX_PATROL_TARGET = 10
PLAN_GEMS = 'known_gems'
PLAN_COMPUTED = 'computed_gems'
PLAN_SIGNAL = 'potential_gems'
PLAN_UNKNOWN = 'exploration'
PLAN_OPPONENTS = 'opponents'
PLAN_PATROL = 'patrol'
PLAN_ANTENNA = 'antenna'
#endregion
#region quadrants
NW = 'North-West'
NE = 'North-East'
SW = 'South-West'
SE = 'South-East'
#endregion

class field_type(Enum):
    unknown = 10
    field = 1
    wall = 100
class log_level(Enum):
    DEBUG = 1
    INFO = 2
    WARNING =3
    ERROR =4
    DEVELOP = 5
    GAME =6

LOG_LEVEL = log_level.INFO
#region Static tools
def log(message:str,log_level_value:log_level=log_level.INFO):
    '''
        Logs a message to stderr with the given log level
    '''
    if log_level_value.value >= LOG_LEVEL.value:
        print(f'[{log_level_value.name}] {message}',file=sys.stderr,flush=True)
def euclidian_distance(pos_a:tuple[int,int],pos_b:tuple[int,int])->float:
    return np.sqrt((pos_a[0]-pos_b[0])**2+(pos_a[1]-pos_b[1])**2)


#endregion


class World:
    def __init__(__self__):
        __self__.field = None
        __self__.width = -1
        __self__.heigth = -1
        __self__.world_changed = True
        __self__.bot_pos = None
        __self__.visible_fields:dict[tuple[int,int]:set[tuple[int,int]]] = {}#Dict for position to view other positions
        __self__.gems_seen = {}
        __self__.fields_seen = {}
    def update_config(__self__,width:int,height:int):
        __self__.field = np.ones((height,width),dtype=np.int16)
        __self__.field *= field_type.unknown.value
        __self__.width = width
        __self__.height = height
        __self__.mid_width = width//2
        __self__.mid_height = height//2
        __self__.world_changed = True
        __self__.antenna_positions = {NW: (__self__.mid_height//2,__self__.mid_width//2),
                                      SE: ((3*__self__.mid_height)//2,(3*__self__.mid_width)//2),
                                      NE: (__self__.mid_height//2,(3*__self__.mid_width)//2),
                                      SW: ((3*__self__.mid_height)//2,__self__.mid_width//2)}
    def update_walls(__self__,data:list):
        value_before = np.sum(data)
        for wall in data:
            __self__.field[wall[1],wall[0]] = field_type.wall.value
        value_after = np.sum(data)
        if value_after != value_before:
            __self__.world_changed = True
            log('Changing world (new Walls).')
    def update_floor(__self__,data:list):
        value_before = np.sum(data)
        __self__.fields_seen ={k:v+1 for k,v in __self__.fields_seen.items()}
        for floor in data:
            __self__.field[floor[1],floor[0]] = field_type.field.value
            __self__.fields_seen[(floor[1],floor[0])] = 0
        value_after = np.sum(data)
        if value_after != value_before:
            __self__.world_changed = True
            log('Changing world (new Floor).')
        log(f'Floor update done, new count: {np.unique(__self__.field,return_counts=True)}')
        __self__.update_fields(__self__.bot_pos,data)
    def update_fields(__self__,current_pos:tuple[int,int],data:list):
        log(f'Number of new Data points: {len(data)}')
        if current_pos in __self__.visible_fields:
            return #No update necessary
        __self__.visible_fields[current_pos] = [(x[1],x[0]) for x in data]
    def update_gems(__self__,data:list):
        value_before = len(__self__.gems_seen)        
        for pos in __self__.visible_fields[__self__.bot_pos]:
            __self__.gems_seen.pop(pos,None)
        for gem in data:
            __self__.gems_seen[(gem['position'][1],gem['position'][0])] = gem['ttl']
        value_after = len(__self__.gems_seen)
        if value_before != value_after:
            __self__.world_changed = True
            log('Changing world (new Gems).')
        log(f'There are currently {len(__self__.gems_seen)} Gems in the list')

class Planer:
    def __init__(__self__,world:World):
        __self__.world = world
        __self__.targets_changed = True
        __self__.first_signal = True
        __self__.signal_radius = 0.0
        __self__.targets = {}
        __self__.computed_not_in_counter = 0
        __self__.gems_computed:set[tuple[int,int]] = set()
        __self__.singal_memory = []
        __self__.current_path:list[tuple[int,int]] = []
        __self__.signal_map = np.zeros_like(__self__.world.field)
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
    def not_implemented_yet(__self__):
        log('This Plan is not implemented yet')
    def path_planing(__self__,start:tuple[int,int],target:tuple[int,int]) -> tuple[list[tuple[int,int]],int]:
        '''
        This uses the dijkstra algorithm to find the shortest path to a given target
        
        :param __self__: Planer instance
        :param startDescription: Poistion to start for search, usually the positon of a bot
        :type start: tuple[int, int]
        :param target: Position of the target, am empty field or gem
        :type target: tuple[int, int]
        :return: List of Fields to touch in row to reach to goal, as well as the costs to reach it
        :rtype: tuple[list[tuple[int, int]], int]
        '''
        f = __self__.world.field
        q = deque()
        q.append((0,start))
        current_path = {}
        score = defaultdict(lambda:float('inf'))
        score[start] = 0
        while q:
            dist,current = q.popleft()
            if target == current:
                break#found destination
            for dx,dy in DIRS.values():
                next = (current[0]+dx,current[1]+dy)
                if next == target:
                    current_path[next] = current
                    q.clear()
                    q.append((0,next))
                    break
                x = next[0]
                y = next[1]
                # bounds check
                if x < 0 or x >= __self__.world.height or y < 0 or y >= __self__.world.width:
                    continue
                # skip walls
                if f[x,y] == field_type.wall.value:
                    continue
                tentative_score = score[current]+f[x,y]#sums current costs and cost for next field
                if tentative_score < score[next]:
                    current_path[next] = current
                    score[next] = tentative_score
                    q.append((tentative_score,next))
        #create the path from the end to start:
        if target not in current_path:
            return [], np.inf# No path found
        actual_path = [target]
        while target in current_path:
            target = current_path[target]
            actual_path.append(target)
        actual_path.reverse()
        final_score = max([v for k,v in score.items() if k in actual_path])
        return actual_path, final_score
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
        log('Starting multi channel singal analysis')
        if not isinstance(signals,list):
            log(f'Could not handle singal of type {type(signals)}, clean up and skip calculation')
            __self__.signal_map *= 0.0
            __self__.targets.get(PLAN_COMPUTED,[]).clear()
            return
        #Compute distances and distributions for each channel
        prev_mem = None if len(__self__.singal_memory) < 2 else __self__.singal_memory[-2]
        cur_mem = __self__.singal_memory[-1]
        cur_mem['channels'] = signals
        cur_mem['distribution'] = []
        cur_mem['distances'] = []
        cur_mem['targets'] = []
        for i in range(len(signals)):
            last_signal_distribution = np.zeros_like(__self__.world.field,np.float64) if prev_mem == None else prev_mem['distribution'][i]
            if signals[i] <= 0:
                last_signal_distribution = np.zeros_like(__self__.world.field,np.float64)
            else:
                log(f'Channel {i} has signal strength {signals[i]}')
            cur_mem['distances'].append(__self__.signal_level_to_distance(signals[i]))
            signal_distribution = __self__.gaussian_distance_ring(__self__.world.bot_pos,cur_mem['distances'][-1],sigma=SIGMA)
            signal_distribution = SIGNAL_MAP_DECAY * last_signal_distribution + (1.0-SIGNAL_MAP_DECAY)*signal_distribution
            signal_distribution /= np.max(signal_distribution)
            signal_distribution = np.nan_to_num(signal_distribution,nan=0.0)
            cur_mem['distribution'].append(signal_distribution)
            max_val = np.max(signal_distribution)
            cur_mem['targets'].append({(x,y) for  x,y in np.argwhere(signal_distribution>max_val*COPUTE_THREASHOLD)})
            folder_path = f'data/{i}/'
            if os.path.exists(folder_path):
                np.savetxt(f'{folder_path}{len(__self__.singal_memory):04d}.csv',signal_distribution)
        statistics ={}
        for targets in cur_mem['targets']:
            for t in targets:
                statistics[t] = statistics.get(t,0) + 1
        if len(statistics) > 0:
            max_value = max(statistics.values())
        else:
            max_value = 1
        cur_mem['min_distance_index'] = np.argmin(cur_mem['distances'])
#Variante 1: Entweder single best, oder nur gruppen
#         if max_value <= 1:
# #            min_dist_gem = cur_mem['distribution'][cur_mem['min_distance_index']]
#             __self__.gems_computed = cur_mem['targets'][cur_mem['min_distance_index']]
#             log ('Using single signal for target')
#         else:
#             __self__.gems_computed = {k for k,v in statistics.items() if v == max_value}            
#             log ('Using multiple signales for targets')
        __self__.gems_computed = set(cur_mem['targets'][cur_mem['min_distance_index']])
        if max_value > 1:
            __self__.gems_computed.update({k for k,v in statistics.items() if v == max_value})            
            log ('Using multiple signales for targets')
        if __self__.gems_computed == None or len(__self__.gems_computed) == 0:
            return
        __self__.targets[PLAN_COMPUTED] = list(sorted(__self__.gems_computed,key=lambda x: euclidian_distance(x,__self__.world.bot_pos)))
        if prev_mem != None and cur_mem['min_distance_index'] != prev_mem['min_distance_index']:
            log('Distance index has changed, need to recompute path.')
            __self__.targets_changed = True
            log(f'New computed area has {len(__self__.targets.get(PLAN_COMPUTED,[]))} potential gems.')
        else:
            log('Check if current path is within targets.')
            num_overlaps = set(__self__.current_path).intersection(set(__self__.targets.get(PLAN_COMPUTED,[])))
            if len(num_overlaps) == 0:
                log('Current path is not within targets, need to recompute path.')
                __self__.targets_changed = True    
        walls = {(x,y) for x,y in np.argwhere(__self__.world.field == field_type.wall.value)}
        visible = set(__self__.world.visible_fields[__self__.world.bot_pos])
        __self__.targets[PLAN_COMPUTED] = [t for t in __self__.targets.get(PLAN_COMPUTED,[]) if t not in walls and t not in visible]

                       

    def analyse_signal(__self__,singal_strength:float|list[float]):
        if isinstance(singal_strength,float):
            if singal_strength <= 0:
                log('Discarding Singal analysis.')
                return
            log('Starting Global Singal analysis.')
            base_distance = __self__.signal_level_to_distance(singal_strength) 
            distances = [(1.0/x) * base_distance for x in GAUS_RING_INTERVALS]
        elif isinstance(singal_strength,list):
            log('Starting channel singal analysis')
            distances = [__self__.signal_level_to_distance(x) for x in singal_strength if x > 0]
        else:
            log(f'Could not handle singal of type {type(singal_strength)}, clean up and skip calculation')
            __self__.signal_map *= 0.0
            __self__.targets.get(PLAN_COMPUTED,[]).clear()
            __self__.first_signal = True
            return
        np.nan_to_num(__self__.signal_map,copy=False,nan=0.0)
        if len(__self__.targets.get(PLAN_COMPUTED,[])) < len(distances):
            __self__.first_signal = True
        signal_map = np.zeros_like(__self__.world.field,np.float64)
        for d in distances:
            signal_map += __self__.gaussian_distance_ring(__self__.world.bot_pos,d,sigma=SIGMA)
        signal_map /= np.max(signal_map)
        if __self__.first_signal:
            __self__.first_signal = False
            __self__.signal_map = signal_map
        else:
            __self__.signal_map = SIGNAL_MAP_DECAY * __self__.signal_map + (1.0-SIGNAL_MAP_DECAY)*signal_map
        __self__.signal_map/=np.max(__self__.signal_map)
        __self__.signal_map[__self__.signal_map < SIGNAL_THRESHHOLD] = 0
        log(f'Max value on singal map: {np.max(__self__.signal_map)}')
        folder = 'data'
        if os.path.exists(folder) and LOG_LEVEL.value < log_level.GAME.value:
            np.savetxt(f'{folder}/{len(os.listdir(folder)):04d}.csv',__self__.signal_map)
        elif os.path.exists(folder):
            log(f'Files in {folder}: {len(os.listdir(folder))}')
        __self__.gems_computed = {(x,y) for  x,y in np.argwhere(__self__.signal_map>COPUTE_THREASHOLD)}
        __self__.gems_computed.difference_update({(x,y) for x,y in np.argwhere(__self__.world.field == field_type.wall.value)})
        __self__.gems_computed.difference_update(set(__self__.world.visible_fields[__self__.world.bot_pos]))
        # __self__.singal_memory.append(gems_computed)
        # if len(__self__.gems_computed) == 0:
        #     __self__.signal_map = np.zeros_like(__self__.signal_map)
        # #Clean up already computed gems
        # if PLAN_COMPUTED in __self__.targets:
        #     l = set(__self__.targets[PLAN_COMPUTED])
        #     l.difference_update(__self__.world.visible_fields[__self__.world.bot_pos])
        #     l.difference_update({(x,y) for x,y in np.argwhere(__self__.world.field == field_type.wall.value)})
        __self__.targets[PLAN_COMPUTED] = list(sorted(__self__.gems_computed,key=lambda x: euclidian_distance(x,__self__.world.bot_pos)))
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
class signal_bot:
    def __init__(__self__):
        __self__.world = World()
        __self__.planer = Planer(__self__.world)
        __self__.first_tick = True
    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line)
            __self__.planer.new_tick()
            __self__.analyse(data)
            __self__.planer.plan_global()
            __self__.select_move()
    def analyse(__self__,data:dict):
        # with open('file.json','w') as f:
        #     json.dump(data,f)
        __self__.world.world_changed = False
        if __self__.first_tick:
            __self__.analyse_first_tick(data)
        __self__.analyse_bot(data)
        __self__.world.update_walls(data.get("wall",[]))
        __self__.world.update_floor(data.get("floor",[]))
        __self__.world.update_gems(data.get('visible_gems',[]))
        # __self__.planer.analyse_signal(data.get('signal_level',0))
        #__self__.planer.analyse_signal(data.get('channels',data.get('singal_level',0)))
        if 'channels' in data:
            __self__.planer.analyse_multi_signal(data.get('channels',[]))
        elif 'antenna_singals' in data:
            __self__.planer.analyse_antenna_signal(data.get('antenna_singals',[]))
    def analyse_first_tick(__self__,data):
        log('First Tick',log_level.DEBUG)
        __self__.first_tick = False
        __self__.world.update_config(width=data['config']['width'],height = data['config']['height'])
        __self__.planer.signal_radius  = data['config']["signal_radius"]
        __self__.planer.max_antenna = data['config'].get("max_antennas",-1)
        __self__.planer.set_antenna = 0
        __self__.planer.target_antenna_num = min(2,__self__.planer.max_antenna) 
        log(f'Setting target antenna num to {__self__.planer.target_antenna_num}')
    def analyse_bot(__self__,data):
        pos = data['bot']
        __self__.world.bot_pos = (pos[1],pos[0])
    def highlight_targets(__self__)->str:
        if LOG_LEVEL == log_level.GAME:
            return ''
        maps = {}
        highlight = []
        if PLAN_UNKNOWN in __self__.planer.targets and __self__.planer.targets[PLAN_UNKNOWN]:
            for pos in __self__.planer.targets[PLAN_UNKNOWN]:
                highlight.append([int(pos[1]),int(pos[0]),'#FFFFFF'])
        for pos in __self__.planer.current_path:
            highlight.append([int(pos[1]),int(pos[0]),'#F00000'])
        if PLAN_COMPUTED in __self__.planer.targets and __self__.planer.targets[PLAN_COMPUTED]:
            for pos in __self__.planer.targets[PLAN_COMPUTED]:
                highlight.append([int(pos[1]),int(pos[0]),'#00FF00'])
            y,x = __self__.planer.targets[PLAN_COMPUTED][0]
            highlight.append([int(x),int(y),'#991199'])
        maps['highlight'] = highlight
        return ' ' + json.dumps(maps)
    def select_move(__self__):
        if __self__.planer.next_antenna != None and len(__self__.planer.current_path) == 1:
            log(f'Moving towards antenna {__self__.planer.next_antenna} at position {__self__.world.antenna_positions[__self__.planer.next_antenna]}')
            direction = (np.sign(__self__.world.antenna_positions[__self__.planer.next_antenna][0]-__self__.world.bot_pos[0]),np.sign(__self__.world.antenna_positions[__self__.planer.next_antenna][1]-__self__.world.bot_pos[1]))
            log(f'selected direction: {direction}')
            move = f'PA{DIRS_INV[direction]}'
            bp = __self__.world.bot_pos 
            if move != 'PAWAIT':
                __self__.planer.antenna_placed[__self__.planer.next_antenna] += 1
                nd = DIRS[DIRS_INV[direction]]
                xxx = (bp[0]+nd[0],bp[1]+nd[1])
                __self__.world.fields_seen.pop(xxx,None)
                log(f'bot will move to {xxx}')
            __self__.planer.next_antenna = None
        elif __self__.planer.current_path:
            log(f'Path length: {len(__self__.planer.current_path)}')
            next_pos = __self__.planer.current_path[0]
            del __self__.planer.current_path[0]
            log(f'next_pos: {next_pos}')
            log(f'bot_pos: {__self__.world.bot_pos}')
            direction =(next_pos[0]-__self__.world.bot_pos[0],next_pos[1]-__self__.world.bot_pos[1])
            log(f'selected direction: {direction}')
            move = DIRS_INV[direction]
        else:
            move = random.choice(list(DIRS.keys()))
            __self__.planer.current_path.clear()
        if move == 'WAIT':
            __self__.planer.current_path.clear()
        print(f'{move}{__self__.highlight_targets()}',flush=True)