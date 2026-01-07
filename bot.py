#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor
from functools import reduce
import operator

import os
import sys, json, random
from collections import deque
import numpy as np
import copy
from uuid import uuid4

from enum import Enum

USE_MULTITHREADING = True
DECAY_FACTOR = 0.8
DECAY_CHANGE = 0.9
OPPONENT_PENALTY_TTL = 0.01
NOT_SEEN_FIELDS = 7
NOT_SEEN_THREASHOLD = 100
EXPLORATION_FIELD_VALUE = 100
POSSIBLE_GEM_VALUE = 10
CYCLING_RELEVANT_FIELDS = 20
MAX_CYCLING_OCCOURENCES = 3
STEP_REDUCE = 20
MAP_STOP_DISTANCE = 4000
MAX_EXLORATION_FIELDS = 20
EPS = 1e-6

random.seed(1)
class log_level(Enum):
    DEBUG = 1
    INFO = 2
    WARNING =3
    ERROR =4
    DEVELOP = 5
    GAME =6

class gem_bot:
    '''
        Gem Bot is a second implementation for the game hidden gems.
    '''
    def __init__(__self__):
        #Game Config
        __self__.visibility_range = 100
        __self__.max_gems = 0
        __self__.use_signal = False
        __self__.signal_radius = 1
        __self__.gem_duration = 1000
        #Base Config
        __self__.current_log_level = log_level.DEBUG
        __self__.decay_factor = DECAY_FACTOR
        __self__.map_max_distance = MAP_STOP_DISTANCE
        # Current State
        __self__.first_tick = True
        __self__.current_tick = 0
        __self__.current_pos = (0,0)
        __self__.current_map = None
        __self__.field_changed = False
        __self__.field = None # Distance map from robot     
        __self__.cycling_detected = False
        # Memory (more than move)
        __self__.walls = None #Map where each wall is set to 0, free space and unknown to 1
        __self__.anchor_views = dict() # For each position, store which other positions could be seen
        __self__.unseen_fields = set()
        __self__.void_fields = set()
        __self__.last_seen_fields = dict()
        __self__.opponents = set()
        __self__.gems = dict()
        __self__.gem_options = dict()  
        __self__.floor_tiles = set()
        __self__.current_targets = list()
        __self__.last_position = None
        __self__.path_history = []

    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line) #
            __self__.analyse(data)
            # __self__.plan()
            __self__.plan_v2()
            __self__.select_move()
    #region analyse data
    def analyse(__self__,data):
        if __self__.first_tick:
            __self__.__analyse_first_tick(data)
        __self__.current_tick = data.get("tick")
        __self__.current_pos = (data['bot'][0],data['bot'][1])
        __self__.field_changed = False
        __self__.__analyse_bot()
        __self__.__analyse_walls(data.get("wall",[]))
        __self__.__analyse_floor(data.get("floor",[]))
        __self__.__analyse_openents(data.get("visible_bots",[]))
        __self__.__analyse_gems(data.get('visible_gems',[]))  
        # __self__.__analyse_singal(data.get('signal_level',0))      
    def __analyse_first_tick(__self__,data):
        __self__.log('First Tick',log_level.DEBUG)
        __self__.first_tick = False
        __self__.field_changed = True
        __self__.width = data['config']['width']
        __self__.height = data['config']['height']
        __self__.max_ticks = data['config']["max_ticks"]
        __self__.visibility_range = data['config']["vis_radius"]
        __self__.max_gems = data['config']["max_gems"]
        __self__.gem_duration = data['config']["gem_ttl"]
        __self__.use_signal = data['config']["emit_signals"]
        __self__.signal_radius = data['config']["signal_radius"]
        __self__.walls = np.ones((__self__.height,__self__.width))
        for x in range(__self__.width):
            for y in range(__self__.height):
                __self__.unseen_fields.add((x,y))
    def __analyse_bot(__self__):
        # Checks the bot position if it affects any changes in plan
        if __self__.current_pos in __self__.gems:
            __self__.log(f'Collected gem at {__self__.current_pos}',log_level.INFO)
            __self__.field_changed = True
        if __self__.current_pos in __self__.current_targets:
             __self__.log(f'Reached target at {__self__.current_pos}',log_level.INFO)
             __self__.field_changed = True
        if __self__.last_position == __self__.current_pos:
            __self__.log(f'Bot did not move from {__self__.current_pos}',log_level.WARNING)
            __self__.field_changed = True
        __self__.last_position = __self__.current_pos
        __self__.path_history.append(__self__.current_pos)
    def __analyse_walls(__self__,walls:list):
        for wall in walls:
            if __self__.walls[wall[1],wall[0]] != 0:
                __self__.field_changed = True
            __self__.walls[wall[1],wall[0]] = 0 # Set the mask to 0 for walls
            if (wall[0],wall[1]) in __self__.unseen_fields:
                __self__.unseen_fields.remove((wall[0],wall[1]))
    def __analyse_floor(__self__,floor_tiles:list):
        #Add Field with a list of all visible fields to the anchor list
        anchor = __self__.anchor_views.get(__self__.current_pos,set())
        if __self__.current_pos not in __self__.anchor_views:
            __self__.field_changed = True
            for tile in floor_tiles:
                tile = tuple(tile)
                anchor.add(tile)
                __self__.unseen_fields.discard(tile)
                if tile in __self__.void_fields:
                    __self__.void_fields.discard(tile)
                    __self__.last_seen_fields[tile] = __self__.current_tick
                    __self__.walls[tile[1],tile[0]] = 1
                    __self__.unseen_fields.add(tile)
            __self__.anchor_views[__self__.current_pos] = anchor
        __self__.floor_tiles.update(anchor)
        #Remove all void fields from unseen fields
        if __self__.unseen_fields:
            for tile in __self__.void_fields:
                __self__.unseen_fields.discard(tile)
        #Update when a field was seen last
        __self__.last_seen_fields = {pos:0 if pos in anchor else __self__.last_seen_fields.get(pos,0)+1 for pos in __self__.floor_tiles}
        #Decrease time, in case robot is running cycles, only relevant if an oponent is there
        __self__.cycling_detected = False
#        if __self__.opponents:
        max_time = max (__self__.last_seen_fields.values())
        last_field_list = __self__.path_history[-min(__self__.current_tick,CYCLING_RELEVANT_FIELDS):]
        last_field_set = set(last_field_list)
        last_field_dict = [last_field_list.count(field) for field in last_field_set]
        if any([occourence > MAX_CYCLING_OCCOURENCES for occourence in last_field_dict]):
            __self__.log(f'Detected cycling in last path: {last_field_list}',log_level.WARNING)
            __self__.cycling_detected = True
        if __self__.cycling_detected:
            __self__.decay_factor = __self__.decay_factor * DECAY_CHANGE
            __self__.map_max_distance = __self__.map_max_distance + 5
            __self__.field_changed = True
            __self__.log(f'Cycling detected, reduced decay factor to {__self__.decay_factor} and map_max_distance to {__self__.map_max_distance}',log_level.INFO)
            for cycle_field in [field for field,value in __self__.last_seen_fields.items() if value == max_time]:
                __self__.last_seen_fields[cycle_field] -= min(STEP_REDUCE, __self__.last_seen_fields[cycle_field])
                __self__.log(f'Reduced not seen time for field {cycle_field} to {__self__.last_seen_fields[cycle_field]}',log_level.INFO)
        else:
            __self__.decay_factor = DECAY_FACTOR
            __self__.map_max_distance = MAP_STOP_DISTANCE
            __self__.log(f'No cycling detected, reset decay factor to {DECAY_FACTOR} and map_max_distance to {MAP_STOP_DISTANCE}',log_level.INFO)
    def __analyse_openents(__self__,opponents:list):
        __self__.opponents.clear()
        for opp in opponents:
            __self__.field_changed = True
            __self__.opponents.add((opp['position'][0],opp['position'][1]))
            __self__.log(f'Found opponent at {opp["position"]}',log_level.INFO)
    def __analyse_gems(__self__,gems:list):
        temp_gem_keys = list(__self__.gems.keys())
        #Remove Gems from visible positions
        for visible_field in __self__.anchor_views[__self__.current_pos]:
            __self__.gems.pop(visible_field,None)
        #Decrease each seen gem
        for k,v in __self__.gems.items():
            __self__.gems[k] = v - 1 #Decrease value by 1 point
        __self__.gems = {k:v for k,v in __self__.gems.items() if v > 0} #Remove all gems with ttl 0
        #Add new Gems
        for gem in gems:
            gem_pos = tuple(gem['position'])
            __self__.log(f'Found gem at {gem_pos} with ttl {gem["ttl"]}',log_level.INFO)
            __self__.gems[gem_pos] = gem['ttl']
            if gem_pos not in temp_gem_keys:
                __self__.field_changed = True
    def __singal_distance_to_signal_level(__self__,distance:float)->float:
        if not __self__.use_signal:
            return 0
        # Distance formula
        # s = 1 / (1 + (d/r)²)
        # With d = distance, r = __self__.signal_radius, s = signal_level
        signal_level = 1 / (1 + (distance/__self__.signal_radius)**2)
        signal_level = np.round(signal_level,6)
        return signal_level
    def __signal_singal_level_to_distance(__self__,signal_level:float)->float:
        if not __self__.use_signal:
            return float('inf')
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
            __self__.log(f'Invalid signal level {signal_level}, returning inf distance',log_level.ERROR)
            return float('inf')
        if signal_level == 0:
            __self__.log(f'Signal level is 0, returning inf distance',log_level.INFO)
            return float('inf')
        distance = __self__.signal_radius * ((1 - signal_level)/signal_level)**0.5
        return distance
    def __analyse_singal(__self__,signal_level:float):
        if not __self__.use_signal:
            return
        #Remove all known singals
        for gem in __self__.gems.keys():
            gem_dist = __self__.calc_distance(gem,__self__.current_pos)
            gem_singal_strength = __self__.__singal_distance_to_signal_level(gem_dist)
            signal_level -= gem_singal_strength
            __self__.log(f'Removed known gem at {gem} with distance {gem_singal_strength} from signal level, new signal level {signal_level}',log_level.DEBUG)
        if signal_level > 1:
            __self__.log(f'Invalid signal level {signal_level}, ignoring',log_level.ERROR)
            return
        if signal_level <= 0:
            __self__.log(f'Signal level is 0, no gem in range, abort singal analysis',log_level.INFO)
            return
        distance = __self__.__signal_singal_level_to_distance(signal_level)
        __self__.log(f'Signal level {signal_level} indicates a gem at distance {distance}',log_level.INFO)
        #Distance is hypotenuse of an rectified triangle. Distances in x and y from bot are Karthets
        if distance > __self__.height + __self__.width:
            __self__.log(f'Calculated distance {distance} is larger than map size, ignoring',log_level.WARNING)
            return
        hyptoenuse = distance**2
        if isinstance(hyptoenuse,complex):
            __self__.log(f'type of hyptoenuse before rounding: {type(hyptoenuse)}',log_level.DEVELOP)
            return
        hyptoenuse = round(hyptoenuse)
        __self__.log(f'Calculated hypotenuse: {hyptoenuse}',log_level.DEBUG)
        new_options = set()
        for x in range(1,int(distance)):
            y_squared = np.sqrt( hyptoenuse - x**2)
            if y_squared.is_integer():
                __self__.log(f'Calculating possible gem positions for x distance {x} to {x**2}',log_level.DEBUG)
                __self__.log(f'Calculated y squared: {y_squared}',log_level.DEBUG)
                y = int(y_squared)
                new_options.add( ( __self__.current_pos[0] + x , __self__.current_pos[1] + y ) )
                new_options.add( ( __self__.current_pos[0] + x , __self__.current_pos[1] - y ) )
                new_options.add( ( __self__.current_pos[0] - x , __self__.current_pos[1] + y ) )
                new_options.add( ( __self__.current_pos[0] - x , __self__.current_pos[1] - y ) )
            else:
                __self__.log(f'Y squared {y_squared} is not integer for x distance {x}, skipping',log_level.INFO)
      # Check for new Options, what is not reallistic:
        for opt in new_options:
            singal_values = __self__.gem_options.get(opt,{}).get('singal_values',[])
            tick_values = __self__.gem_options.get(opt,{}).get('tick_values',[])
            singal_values.append(signal_level)
            tick_values.append(__self__.current_tick)
            __self__.gem_options[opt] = {
                'signal_values': singal_values,
                'tick_values': tick_values
            }
        __self__.log(f'Predicted new gems at positions: {new_options}',log_level.INFO)
        #Clean up
        cleanup_keys = set()
        __self__.log(f'Cleaning up gem options, currently {len(cleanup_keys)} options stored',log_level.DEVELOP)
        # cleanup_keys.update(__self__.anchor_views.get(__self__.current_pos,set()))
        timeout_tick = __self__.current_tick - __self__.gem_duration
        for k,v in __self__.gem_options.items():
            #Remove old options
            tick_values = v.get('tick_values',[])
            if k in __self__.void_fields:
                cleanup_keys.add(k)
                __self__.log(f'Removing gem option {k}, marked as void field',log_level.DEBUG)
                continue
            if any([tick < timeout_tick for tick in tick_values]):
                cleanup_keys.add(k)
                __self__.log(f'Removing gem option {k}, too old',log_level.DEBUG)
                continue
            if k not in new_options and len(tick_values) < 2:
                cleanup_keys.add(k)
                __self__.log(f'Removing gem option {k}, not enough signals received yet',log_level.DEBUG)
                continue
            if k[0] < 0 or k[0] >= __self__.width or k[1] < 0 or k[1] >= __self__.height:
                cleanup_keys.add(k)
                __self__.log(f'Ignoring gem option {k}, out of bounds',log_level.DEBUG)
                continue
            if __self__.walls[k[1],k[0]] == 0:
                cleanup_keys.add(k)
                __self__.log(f'Ignoring gem option {k}, wall in the way',log_level.DEBUG)
                continue
        for k in cleanup_keys:
            __self__.gem_options.pop(k,None)
            __self__.log(f'Removed gem option at {k}',log_level.INFO)
    #endregion
    def __get_explorartion_fields(__self__)->list[tuple[int,int]]:
        __self__.log('No gems visible, adding nearest unseen field as target')
        distances = list()
        for x in __self__.unseen_fields:
            distances.append({'loc':x,'dist':__self__.calc_distance(x,__self__.current_pos)}) 
        distances.sort(key=lambda a: a['dist'])
        relevant_elements = list()
        for i in range(min(MAX_EXLORATION_FIELDS,len(distances))):
            relevant_elements.append(distances[i]['loc'])
        return relevant_elements
    def __get_patrol_fields(__self__)->list[tuple[int,int]]:
        # Select field that is last recently seen
        max_time_field_not_seen = sorted(__self__.last_seen_fields.values(),reverse=True)
        max_time_field_not_seen = max_time_field_not_seen[0:min(NOT_SEEN_FIELDS,len(max_time_field_not_seen))]
        __self__.log(f'Max time field not seen: {max_time_field_not_seen}',log_level.INFO)
        max_field = {field for field,not_seen in __self__.last_seen_fields.items() if not_seen == max_time_field_not_seen[0]}.pop()
        __self__.log(f'Fields not seen for max time: {max_field} for {__self__.last_seen_fields[max_field]} ticks',log_level.INFO)
        #Reduce current target if cycling
        relevant_fields = {field for field,not_seen in __self__.last_seen_fields.items() if not_seen in max_time_field_not_seen}
        __self__.log(f'Patrol fields: {len(relevant_fields)}',log_level.DEBUG)
        #Select next field
        # Select by maximum number of fields to see
        anchor_fields = {field:len(value & relevant_fields) for field,value in __self__.anchor_views.items() if len(value & relevant_fields) > 0}
        __self__.log(f'Anchor fields for patrol: {len(anchor_fields)}',log_level.DEBUG)
        max_fields = sorted(anchor_fields.values(),reverse=True)[0]
        anchor_fields = [field for field,value in anchor_fields.items() if value == max_fields]
        relevant_elements = list(anchor_fields)
        __self__.log(f'Selected patrol fields: {len(relevant_elements)}',log_level.DEBUG)
        #In case the max not seen field outrages the threashhold, add the next field, that sees it, if necessary
        if __self__.last_seen_fields.get(max_field,0) > NOT_SEEN_THREASHOLD:
            selected_anchors = [field for field in anchor_fields if max_field in __self__.anchor_views.get(field,set())]
            if not selected_anchors:
                #Find all anchors looking at this field
                all_anchors = [field for field,value in __self__.anchor_views.items() if max_field in value]
                target_distances = __self__.build_field(__self__.current_pos,target_value=1,decay=None)
                sorted_anchors = sorted(all_anchors,key=lambda x:target_distances[x[1],x[0]])
                relevant_elements.append(sorted_anchors[0])
        return relevant_elements
    def __collect_targets(__self__) -> tuple[list[tuple[int,int]],list[int]]:
        '''
            Collect all relevant targets for the field calculation
            Relevant targets are returned as two lists, one with positions, one with values
        '''
        relevant_elements = list()
        relevant_values = list()
        # Add Gems and Opoennts as targets
        for gem_pos,gem_ttl in __self__.gems.items():
            relevant_elements.append(gem_pos)
            relevant_values.append(gem_ttl)
        for opponent in __self__.opponents:
            relevant_elements.append(opponent)
            relevant_values.append(-abs(OPPONENT_PENALTY_TTL))
        for opt in __self__.gem_options.keys():
            relevant_elements.append(opt)
            relevant_values.append(POSSIBLE_GEM_VALUE)
        # Add next unseen field, if no gem exists
        __self__.log(f'Gems: {len(__self__.gems)}, Unseen fields: {len(__self__.unseen_fields)}, Predicted Gems: {len(__self__.gem_options)}',log_level.DEVELOP)
        # In case a cycle is detected, it might not be possible to explore right now.
        if len(__self__.gems) == 0 and len(__self__.unseen_fields)>0 and not __self__.cycling_detected:
            unseen_elements = __self__.__get_explorartion_fields()
            for x in unseen_elements:
                relevant_elements.append(x)
                relevant_values.append(EXPLORATION_FIELD_VALUE)
        # elif len(__self__.gems) == 0 and len(__self__.unseen_fields) == 0:
#        if len(__self__.gems) == 0 and len(__self__.gem_options) == 0:
        patrol_elements = __self__.__get_patrol_fields()
        for x in patrol_elements:
            relevant_elements.append(x)
            relevant_values.append(max(1,__self__.last_seen_fields.get(x,1)))
        # relevant_values.append(1)
        __self__.log(f'Relevant elements: {relevant_elements}',log_level.INFO)
        __self__.current_targets = relevant_elements
        return relevant_elements,relevant_values
    def plan(__self__):
        if not __self__.field_changed:
            __self__.log('Field has not changed, reusing old field',log_level.INFO)
            return
        relevant_elements,relevant_values = __self__.__collect_targets()
        field = None
        if USE_MULTITHREADING:
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                results = list(executor.map(__self__.build_field,relevant_elements,relevant_values))
            field = reduce(operator.add,results)
        else:
            for pos,ttl in zip (relevant_elements,relevant_values):
                single_field = __self__.build_field(pos,ttl)
                if field is None:
                    field = single_field
                else:
                    field += single_field
        if field.any():
            __self__.field = field
        else:
            raise Exception('No field could be built')
        # select way to gem
    def plan_v2(__self__):
        '''
            This planing creates fields for all four possible directions. Afterwards, distance symetry is used to find the values of this fields. 
            Symetry is distance(a,b) == distance(b,a)
        '''
        relevant_elements,relevant_values = __self__.__collect_targets()
        field = np.zeros((__self__.height,__self__.width),dtype=np.float32)
        bot_x = __self__.current_pos[0]
        bot_y = __self__.current_pos[1]
        future_positions = {
            'w' : (bot_x-1,bot_y),
            'n' : (bot_x,bot_y-1),
            'e' : (bot_x+1,bot_y),
            's' : (bot_x,bot_y+1)
        }
        for direction,pos in future_positions.items():
            if pos[0] < 0 or pos[0] >= __self__.width or pos[1] < 0 or pos[1] >= __self__.height:
                continue
            dir_field = __self__.build_field(pos,target_value=1,decay=None,stop_at_distance=1000)
            field_value = 0
            for  target_pos,target_value in zip(relevant_elements,relevant_values):
                field_exp_value = dir_field[target_pos[1],target_pos[0]]
                if field_exp_value == 100:
                    __self__.void_fields.add(target_pos)
                    __self__.gem_options.pop(target_pos,None)
                    continue
                current_field_value = target_value *  __self__.decay_factor ** field_exp_value 
                field_value +=  current_field_value
            field[pos[1],pos[0]] = field_value
            __self__.log(f'Field value for direction {direction} at position {pos} is {field_value}',log_level.DEBUG)
        __self__.field = field


    def build_field(__self__,target:tuple[int,int],target_value:int=1,decay:float|None='use_self',stop_at_distance:int=None)->np.ndarray:
        '''
        This computes the whole field, abort as soon as the position of the bot is reached.
        Formula is target_value * decay**field_value
        
        :param __self__: Description
        :param target: X/Y Position of the target
        :type target: tuple[int, int]
        :param target_value: Multiplyer for field (e.g. GEM TTL, or penality for opponent)
        :type target_value: int
        :param decay: factor for decreasing each value on the field. if None, decay is not calculated
        :type decay: float|None
        '''
        if decay == 'use_self':
            decay = __self__.decay_factor
        if not stop_at_distance:
            stop_at_distance = __self__.map_max_distance
        # Creates the potential field, with all known obstacles, unknown fields are handled as available fields for this
        __self__.log(f'Building field for target at {target} with value {target_value} and decay {decay}',log_level.DEBUG)
        map = np.full((__self__.height, __self__.width), 100, dtype=np.int8)
        q = deque()
        q.append((target[0],target[1], 0))
        early_stopped = False
        while q:
            x, y, dist = q.popleft()
            # bounds check
            if x < 0 or x >= __self__.width or y < 0 or y >= __self__.height:
                continue
            # skip walls
            if __self__.walls[y,x] == 0:
                continue
            # already has a shorter distance
            if map[y, x] <= dist:
                continue
            map[y, x] = dist
            nd = dist + 1
            if nd > stop_at_distance:
                early_stopped = True
                continue
            q.append((x+1, y, nd))
            q.append((x-1, y, nd))
            q.append((x, y+1, nd))
            q.append((x, y-1, nd))
        if not early_stopped and map[__self__.current_pos[1],__self__.current_pos[0]] == 100:
            __self__.void_fields.add(target)
            __self__.log(f'Target at {target} is unreachable, added to void fields',log_level.WARNING)
        if early_stopped:
            __self__.log(f'Field calculation for target at {target} stopped early at distance {stop_at_distance}',log_level.INFO)
        if decay:
            map = target_value * decay ** map
        else:
            map = target_value * map
        return map
    def hightlight_targets(__self__)->str:
        if __self__.current_log_level == log_level.GAME:
            return ''
        maps = {}
        hightlight = []
        maps['highlight'] = hightlight
        for target in __self__.current_targets:
            if target in __self__.gems:
                color = '#FFFF00'
            elif target in __self__.opponents:
                color = '#FF0000'
            else:
                color = '#00FF00'
            hightlight.append([target[0],target[1],color])
        for gem_pos in __self__.gem_options:
            hightlight.append([gem_pos[0],gem_pos[1],"#FF0000"])
        return ' '+json.dumps(maps)
    def select_move(__self__)->str:
        '''
            gathers the four values around the bot, and its values. selects the field with the highest value as next move
        '''
        __self__.log(f'Number of target:{len(__self__.current_targets)}',log_level.DEVELOP)
        map = __self__.field
        bot_x = __self__.current_pos[0]
        bot_y = __self__.current_pos[1]
        directions = {}
        #Map is indexed [y,x] Select the possible next steps
        with open("debug_map.csv","w") as f:
            np.savetxt(f,map,delimiter=";")
        #region west
        w = (bot_y,max(bot_x-1,0))
        if __self__.walls [w[0],w[1]] > 0 and (w[1],w[0]) not in __self__.opponents:
            directions['W']=map[w[0],w[1]]
        #endregion
        #region east
        e = (bot_y,min(bot_x+1,__self__.width-1))
        if __self__.walls [e[0],e[1]] > 0 and (e[1],e[0]) not in __self__.opponents:
            directions['E']=map[e[0],e[1]]
        #endregion
        #region north
        n = (max(bot_y-1,0),bot_x)
        if __self__.walls [n[0],n[1]] > 0 and (n[1],n[0]) not in __self__.opponents:
            directions['N']=map[n[0],n[1]]
        #endregion
        #region south
        s = (min(bot_y+1,__self__.height),bot_x)
        if __self__.walls [s[0],s[1]] > 0 and (s[1],s[0]) not in __self__.opponents:
            directions['S']=map[s[0],s[1]]
        #endregion
        __self__.log(f'Bot position: {bot_x},{bot_y} {directions}',log_level.INFO)  
        if not directions:# Fallback if bot is surrounded
            direction = 'WAIT'
        else:
            direction = max(directions,key=directions.get)
        highlight = __self__.hightlight_targets()
        print(f'{direction}{highlight}',flush=True)
    # Helper
    def log(__self__,message:str,log_level_value:log_level=log_level.INFO):
        '''
            Logs a message to stderr with the given log level
        '''
        if log_level_value.value >= __self__.current_log_level.value:
            print(f'[{log_level_value.name}] {message}',file=sys.stderr,flush=True)
    def calc_distance(__self__,pos1:tuple[int,int],pos2:tuple[int,int])->int:
        '''
            Simple helper function to calulate Manhattan distance
        '''
        return abs(pos1[0]-pos2[0]) + abs(pos1[1]-pos2[1])

if __name__ == "__main__":
    # gem_searcher().main()
  gem_bot().main()
    # bot = gem_bot()
    # bot.width = 12
    # bot.height = 6
    # bot.current_pos = (2,3)
    # bot.walls = np.ones((bot.height,bot.width),dtype=np.int8)
    # bot.walls[5,3] = 0
    # bot.walls[3,3] = 0
    # bot.walls[5,2] = 0
    # bot.walls[4,2] = 0
    # print(bot.build_field((4,4)))
    # print(bot.build_field((4,4),decay=None))
    # bot.anchor_views = {
    #     (2,3): {(1,1),(1,2),(2,1)},
    #     (5,5): {(4,4),(4,5),(5,4)},
    #     (1,5): {(0,4),(0,5),(1,4),(4,5),(7,1),(8,0)},
    #     (8,1): {(7,0),(7,1),(8,0)},
    #     (0,4): {(0,4),(0,5),(1,4)}
    # }
    # print(bot.create_achrons())