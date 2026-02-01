import json
import sys
import random
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
PLAN_GEMS = 'known_gems'
PLAN_COMPUTED = 'computed_gems'
PLAN_SIGNAL = 'potential_gems'
PLAN_UNKNOWN = 'exploration'
PLAN_OPPONENTS = 'opponents'
PLAN_PATROL = 'patrol'
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
        __self__.world_changed = True
    def update_walls(__self__,data:list):
        value_before = np.sum(data)
        for wall in data:
            __self__.field[wall[1],wall[0]] = field_type.wall.value
        value_after = np.sum(data)
        if value_after != value_before:
            __self__.world_changed = True
    def update_floor(__self__,data:list):
        value_before = np.sum(data)
        __self__.fields_seen ={k:v+1 for k,v in __self__.fields_seen.items()}
        for floor in data:
            __self__.field[floor[1],floor[0]] = field_type.field.value
            __self__.fields_seen[(floor[1],floor[0])] = 0
        value_after = np.sum(data)
        if value_after != value_before:
            __self__.world_changed = True
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
        log(f'There are currently {len(__self__.gems_seen)} in the list')
class Planer:
    def __init__(__self__,world:World):
        __self__.world = world
        __self__.targets_changd = True
        __self__.targets = {}
        __self__.current_path:list[tuple[int,int]] = []
        __self__.planing_actions = {
            PLAN_COMPUTED:__self__.not_implemented_yet,
            PLAN_GEMS:__self__.gem_selection,
            PLAN_OPPONENTS:__self__.not_implemented_yet,
            PLAN_PATROL:__self__.patrol_selection,
            PLAN_SIGNAL:__self__.not_implemented_yet,
            PLAN_UNKNOWN:__self__.exploration
        }
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
        return actual_path, score[target]
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
        for i in range(len(combinations)):
            combo = [__self__.world.bot_pos]
            combo.extend(combinations[i])
            distance_score.append(0)
            for j in range(len(combo)-1):
                distance_score[i] += __self__.path_planing(combo[j],combo[j+1])[1]
        min_index = np.argmin(distance_score)
        __self__.targets[PLAN_GEMS] = combinations[min_index]
        log(f'Found {len(combinations)} gem combinations')
    def patrol_selection(__self__):
        '''
            This selects the next position to see a field, that is not for longest time.
        '''
        max_not_seen_value = max(__self__.world.fields_seen.values())
        relevant_fields = {k for k,v in __self__.world.fields_seen.items() if v == max_not_seen_value}
        log(f'Patrol Relevant Targets: {relevant_fields}')
        possible_targets = {k for k,v in __self__.world.visible_fields.items() if len(relevant_fields.intersection(v)) > 0}
        log(f'Patrol Possible Targets: {possible_targets}')
        target_values =  {k:__self__.path_planing(__self__.world.bot_pos,k)[1] for k in possible_targets}
        __self__.targets[PLAN_PATROL] = list(k for k,v in sorted(target_values.items(),key=lambda item:item[1]))
        log(f'Patrol Fields: {__self__.targets[PLAN_PATROL]}')
    def plan_global(__self__):
        if __self__.current_path and not (__self__.world.world_changed and __self__.targets_changd):
            log('Use existing path')
            return
        log('Calculating new Path')
        plan_order = [
            PLAN_GEMS,
            PLAN_UNKNOWN,
            PLAN_COMPUTED,
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
                break

class signal_bot:
    def __init__(__self__):
        __self__.world = World()
        __self__.planer = Planer(__self__.world)
        __self__.first_tick = True
    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line) #
            __self__.analyse(data)
            __self__.planer.plan_global()
            __self__.select_move()
    def analyse(__self__,data:dict):
        __self__.world.world_changed = False
        if __self__.first_tick:
            __self__.analyse_first_tick(data)
        __self__.analyse_bot(data)
        __self__.world.update_walls(data.get("wall",[]))
        __self__.world.update_floor(data.get("floor",[]))
        __self__.world.update_gems(data.get('visible_gems',[]))
    def analyse_first_tick(__self__,data):
        log('First Tick',log_level.DEBUG)
        __self__.first_tick = False
        __self__.world.update_config(width=data['config']['width'],height = data['config']['height'])
    def analyse_bot(__self__,data):
        pos = data['bot']
        __self__.world.bot_pos = (pos[1],pos[0])
    def highlight_targets(__self__)->str:
        if LOG_LEVEL == log_level.GAME:
            return ''
        maps = {}
        highlight = []
        for pos in __self__.planer.targets[PLAN_UNKNOWN]:
            highlight.append([int(pos[1]),int(pos[0]),'#FFFFFF'])
        for pos in __self__.planer.current_path:
            highlight.append([int(pos[1]),int(pos[0]),'#F00000'])
        # highlight.append([27,38,'#61FF45'])
        # highlight.append([27,39,'#61FF45'])
        # highlight.append([38,27,'#61FF45'])
        # highlight.append([39,27,'#61FF45'])
        maps['highlight'] = highlight
        return ' ' + json.dumps(maps)
    def select_move(__self__):
        if __self__.planer.current_path:
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
        print(f'{move}{__self__.highlight_targets()}',flush=True)