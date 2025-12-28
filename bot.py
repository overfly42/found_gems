#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor
import os
import sys, json, random
from collections import deque
import numpy as np
import copy
from uuid import uuid4

from enum import Enum


DEBUG = False
MAX_DISTANCE = 2
DECAY_FACTOR = 0.8
NUMBER_OF_LAST_POSITIONS = 0
OPPONENT_PENALTY_TTL = 5


random.seed(1)
class gem_searcher:
    def __init__(__self__):
        __self__.config = {}
        __self__.width = 0
        __self__.height = 0
        __self__.first_tick = True
        __self__.current_tick = 0
        __self__.max_ticks = 0
        __self__.last_positions = []
        __self__.folder = str(uuid4())
        __self__.walls = None
        __self__.gems = {}
        __self__.known_walls = set()
        __self__.visible_fields = []
        __self__.current_target = None
        __self__.target_not_reached_counter = 10
        __self__.last_seen_fields = {}
        __self__.unseen_fields = set()
        __self__.void_fields = set()
        __self__.all_fields = set()
        __self__.view_positions = dict()
        if DEBUG:
            import os
            os.makedirs(__self__.folder,exist_ok=True)
    def main(__self__):
        for line in sys.stdin:
            __self__.log('----------------')
            data = json.loads(line)

            __self__.analyse_json(data)
            map = __self__.build_map()
            if DEBUG:
                np.savetxt(f"{__self__.folder}/data_{__self__.current_tick:05}.csv",map,delimiter=";")
            
            move = __self__.select_move(map)
            print(move, flush=True)

    def log(__self__,message):
        '''Writes to STD ERR if DEBUG is enabled'''
        if DEBUG:
            print(message,file=sys.stderr,flush=True)
    def store(__self__,value,prefix:str='data'):
        '''Stores the bot state to a file if DEBUG is enabled. Each file is numbered sequentially'''
        if DEBUG:
            with open(f"{__self__.folder}/{prefix}_bot_state{__self__.current_tick:05}.json","w") as f:
                json.dump(value,f)

    def calc_distance(__self__,pos1:tuple[int,int],pos2:tuple[int,int])->int:
        '''
            Simple helper function to calulate Manhattan distance
        '''
        return abs(pos1[0]-pos2[0]) + abs(pos1[1]-pos2[1])

    def analyse_json(__self__,data):
        __self__.store(data,'raw')
        if __self__.first_tick:
            __self__.log('First Tick')
            __self__.config = data.get("config", {})
            __self__.width = __self__.config.get("width")
            __self__.height = __self__.config.get("height")
            __self__.max_ticks = __self__.config.get("max_ticks")
            __self__.first_tick = False
            __self__.walls = np.ones((__self__.height,__self__.width))
            for x in range(__self__.width):
                for y in range(__self__.height):
                    __self__.all_fields.add((x,y))
        __self__.current_tick = data.get("tick")
        __self__.opponents = [x['position'] for x in data.get("visible_bots",[])]
        my_pos = {'bot':data['bot'],"visible_gems":data.get("visible_gems",None)}
        __self__.last_positions.append(my_pos['bot'])
        for wall in data.get('wall'):
            __self__.walls[wall[1],wall[0]] = 0
            __self__.known_walls.add((wall[0],wall[1]))
        __self__.visible_fields = {(x[0],x[1]) for x in data.get('floor')}
        for field in __self__.last_seen_fields.keys():
            __self__.last_seen_fields[field] = 0 if field in __self__.visible_fields else __self__.last_seen_fields[field] + 1
        for field in __self__.visible_fields:
            __self__.last_seen_fields[field] = 0
            data_element = __self__.view_positions.get(field,set())
            data_element.add((data['bot'][0],data['bot'][1]))
            __self__.view_positions[field] = data_element
        __self__.unseen_fields = set(__self__.all_fields - set(__self__.last_seen_fields.keys()) - __self__.known_walls - __self__.void_fields)
        __self__.log(f'Unseen fields: {len(__self__.unseen_fields)}, void fields: {len(__self__.void_fields)}')
        if len(__self__.last_positions) > NUMBER_OF_LAST_POSITIONS:
            __self__.last_positions.pop(0)
        for gem in __self__.gems.values():
            gem['ttl'] -= 1
        outdated_gems = [key for key,gem in __self__.gems.items() if gem['ttl'] <= 0]
        outdated_gems.extend([key for key,gem in __self__.gems.items() if gem['x_gem'] == my_pos['bot'][0] and gem['y_gem'] == my_pos['bot'][1]])
        for key in outdated_gems:
            __self__.gems.pop(key)
        for gem in my_pos["visible_gems"]:
            __self__.gems[(gem['position'][0],gem['position'][1])] = {
            'x_gem': gem['position'][0],
            'y_gem': gem['position'][1],
            'ttl': gem['ttl'],
            'distance_to_oppeent': min([__self__.calc_distance(gem['position'],opp) for opp in __self__.opponents]) if __self__.opponents else float('inf'),
            'distance':__self__.calc_distance(my_pos['bot'], gem['position'])
            }
        __self__.my_pos = my_pos

    def build_single_map(__self__,gem):
        '''
            Build a distance decay map for a single gem. Most victory_points are near the gem, decaying with manhatten distance
        '''
        if not __self__.known_walls:
            __self__.log('No known walls, using simple distance map')
            x0 = gem['x_gem']
            y0 = gem['y_gem']
            x = np.arange(__self__.width)
            y = np.arange(__self__.height)[:,None]
            map = np.abs(x - x0) + np.abs(y - y0)
        else:
            map = np.full((__self__.height, __self__.width), 100, dtype=np.int8)
            q = deque()
            q.append((gem['x_gem'], gem['y_gem'], 0))
            while q:
                x, y, dist = q.popleft()
                # bounds check
                if x < 0 or x >= __self__.width or y < 0 or y >= __self__.height:
                    continue
                # skip walls
                if (x, y) in __self__.known_walls:
                    continue
                # already has a shorter distance
                if map[y, x] <= dist:
                    continue
                map[y, x] = dist
                nd = dist + 1
                q.append((x+1, y, nd))
                q.append((x-1, y, nd))
                q.append((x, y+1, nd))
                q.append((x, y-1, nd))
            # After map is built, check if the bot could reach the goal, else add to void fields
            if map[__self__.my_pos['bot'][1],__self__.my_pos['bot'][0]] == 100:
                __self__.void_fields.add((gem['x_gem'],gem['y_gem']))
                map = np.full((__self__.height, __self__.width), 100, dtype=np.int8)

        map = gem['ttl'] * DECAY_FACTOR**(map)
        return map

    def build_map(__self__,)->np.ndarray:
        '''
            Build a distance decay map for all gems
        '''
        full_map = np.ones((__self__.height,__self__.width))
        # Remove Gems much closer to the opponent than to us
        orderd_gems = sorted(__self__.gems.values(),key=lambda x:x['distance_to_oppeent'] - x['distance'])
        do_remove = len(__self__.opponents) > 0
        enough_gems = len(orderd_gems) > 1
        removal_distance = enough_gems and ((orderd_gems[0]['distance_to_oppeent'] - orderd_gems[0]['distance']) > MAX_DISTANCE)
        if  do_remove and enough_gems and removal_distance:
            __self__.log(f'Removed gem at {orderd_gems[0]["x_gem"]},{orderd_gems[0]["y_gem"]} as too close to opponent')
            orderd_gems.pop(0)
        # Build a map for each gem and add it to the full map
        __self__.log(f'Building map with {len(orderd_gems)} gems')
        for gem in orderd_gems:
            single_map = __self__.build_single_map(gem)
            full_map += single_map*10
        for opp in __self__.opponents:
            single_map = __self__.build_single_map({'x_gem':opp[0],'y_gem':opp[1],'ttl':OPPONENT_PENALTY_TTL})
            full_map -= single_map
        # Explore unseen areas if no gems are visible
        if not __self__.gems:
            if __self__.unseen_fields:
                __self__.log('No gems visible, exploring unseen fields')
                for field in random.sample(sorted(__self__.unseen_fields),min(10,len(__self__.unseen_fields))):
                    single_map = __self__.build_single_map({'x_gem':field[0],'y_gem':field[1],'ttl':1})
                    full_map += single_map
            else:
                __self__.log('No unseen fields, exploring least recently seen fields')
                max_time_field_not_seen = max(__self__.last_seen_fields.values())
                relevant_fields = [field for field,not_seen in __self__.last_seen_fields.items() if not_seen == max_time_field_not_seen]
                if __self__.current_target not in relevant_fields or __self__.target_not_reached_counter <=0:
                    __self__.current_target = random.choice(relevant_fields)
                __self__.target_not_reached_counter = 10
                view_positions = __self__.view_positions.get(__self__.current_target,None)
                if not view_positions:
                    single_map = __self__.build_single_map({'x_gem':__self__.current_target[0],'y_gem':__self__.current_target[1],'ttl':1})
                    full_map += single_map
                else:
                    __self__.log(f'Using view positions {len(view_positions)} to reach target at {__self__.current_target}')
                    for pos in list(view_positions)[0:min(len(view_positions),10)]:
                        full_map += __self__.build_single_map({'x_gem':pos[0],'y_gem':pos[1],'ttl':1})
        #Set all old positions to 0, to avoid going in circles
        for pos in __self__.last_positions:
            full_map[pos[1],pos[0]] = 0
        # Mask walls
        full_map = full_map * __self__.walls
        return full_map
    def select_move(__self__,map:np.ndarray)->str:
        '''
            gathers the four values around the bot, and its values. selects the field with the highest value as next move
        '''
        bot_x = __self__.my_pos['bot'][0]
        bot_y = __self__.my_pos['bot'][1]
        directions = {}
        #Map is indexed [y,x] Select the possible next steps
        directions['W']=map[bot_y,max(bot_x-1,0)]
        directions['E']=map[bot_y,min(bot_x+1,__self__.width-1)]
        directions['N']=map[max(bot_y-1,0),bot_x]
        directions['S']=map[min(bot_y+1,__self__.height),bot_x]
        __self__.log(f'Bot position: {bot_x},{bot_y} {directions}')    
        return max(directions,key=directions.get)

class log_level(Enum):
    DEBUG = 1
    INFO = 2
    WARNING =3
    ERROR =4
    GAME =5

class gem_bot:
    '''
        Gem Bot is a second implementation for the game hidden gems.
    '''
    def __init__(__self__):
        __self__.current_log_level = log_level.ERROR
        __self__.first_tick = True
        __self__.current_tick = 0
        __self__.current_pos = (0,0)
        __self__.current_map = None
        # Memory (more than move)
        __self__.walls = None #Map where each wall is set to 0, free space and unknown to 1
        __self__.anchor_views = dict() # For each position, store which other positions could be seen
        __self__.unseen_fields = set()
        __self__.void_fields = set()
        __self__.last_seen_fields = dict()
        __self__.field_changed = False
        __self__.field = None # Distance map from robot     
        __self__.opponents = set()
        __self__.gems = dict()   
        __self__.floor_tiles = set()

    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line) #
            __self__.analyse(data)
            __self__.plan()
            __self__.select_move()
    #region analyse data
    def analyse(__self__,data):
        if __self__.first_tick:
            __self__.__analyse_first_tick(data)
        __self__.current_tick = data.get("tick")
        __self__.current_pos = (data['bot'][0],data['bot'][1])
        __self__.field_changed = False
        __self__.__analyse_walls(data.get("wall",[]))
        __self__.__analyse_floor(data.get("floor",[]))
        __self__.__analyse_openents(data.get("visible_bots",[]))
        __self__.__analyse_gems(data.get('visible_gems',[]))        
    def __analyse_first_tick(__self__,data):
        __self__.log('First Tick',log_level.DEBUG)
        __self__.first_tick = False
        __self__.field_changed = True
        __self__.width = data['config']['width']
        __self__.height = data['config']['height']
        __self__.max_ticks = data['config']["max_ticks"]
        __self__.walls = np.ones((__self__.height,__self__.width))
        for x in range(__self__.width):
            for y in range(__self__.height):
                __self__.unseen_fields.add((x,y))
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
            __self__.anchor_views[__self__.current_pos] = anchor
        __self__.floor_tiles.update(anchor)
        #Remove all void fields from unseen fields
        if __self__.unseen_fields:
            for tile in __self__.void_fields:
                __self__.unseen_fields.discard(tile)
        #Update when a field was seen last
        __self__.last_seen_fields = {pos:0 if pos in anchor else __self__.last_seen_fields.get(pos,0)+1 for pos in __self__.floor_tiles}
    def __analyse_openents(__self__,opponents:list):
        if opponents:
            __self__.opponents.clear()
        for opp in opponents:
            __self__.field_changed = True
            __self__.opponents.add((opp['position'][0],opp['position'][1]))
    def __analyse_gems(__self__,gems:list):
        #Remove Gems from visible positions
        for visible_field in __self__.anchor_views[__self__.current_pos]:
            __self__.gems.pop(visible_field,None)
        #Decrease each seen gem
        for k,v in __self__.gems.items():
            if v <= 0:
                __self__.gems.pop(k) # Remove Gems without ticks left
            __self__.gems[k] = v - 1 #Decrease value by 1 point
        #Add new Gems
        for gem in gems:
            __self__.log(f'Found gem at {gem["position"]} with ttl {gem["ttl"]}',log_level.INFO)
            __self__.gems[tuple(gem['position'])] = gem['ttl']
    #endregion
    def __get_explorartion_fields(__self__)->list[tuple[int,int]]:
        __self__.log('No gems visible, adding nearest unseen field as target')
        distances = list()
        for x in __self__.unseen_fields:
            distances.append({'loc':x,'dist':__self__.calc_distance(x,__self__.current_pos)}) 
        distances.sort(key=lambda a: a['dist'])
        relevant_elements = list()
        for i in range(min(20,len(distances))):
            relevant_elements.append(distances[i]['loc'])
        return relevant_elements
    def __get_patrol_fields(__self__)->list[tuple[int,int]]:
        # Select field that is last recently seen
        # max_time_field_not_seen = max(__self__.last_seen_fields.values())
        max_time_field_not_seen = sorted(__self__.last_seen_fields.values(),reverse=True)
        max_time_field_not_seen = max_time_field_not_seen[0:min(7,len(max_time_field_not_seen))]

        relevant_fields = [field for field,not_seen in __self__.last_seen_fields.items() if not_seen in max_time_field_not_seen]
        #Select next field
        target_distances = __self__.build_field(__self__.current_pos,target_value=1,decay=None)
#        max_dist = max(target_distances.flatten())
#        max_anchors = max([len(__self__.anchor_views.get(x,set())) for x in relevant_fields])
#        relevant_field = sorted(relevant_fields,key=lambda x:target_distances[x[1],x[0]]/max_dist + max_anchors/max(1,len(__self__.anchor_views.get(x,set()))))
        relevant_field = sorted(relevant_fields,key=lambda x:target_distances[x[1],x[0]])
#        relevant_field = sorted(relevant_fields,key=lambda x:__self__.calc_distance(x,__self__.current_pos))
        relevant_elements = list()
        for i in range(min(3,len(relevant_field))):
            relevant_elements.append(relevant_field[i])
        return relevant_elements
    def plan(__self__):
        relevant_elements = list()
        relevant_values = list()
        # Add Gems and Opoennts as targets
        for gem_pos,gem_ttl in __self__.gems.items():
            relevant_elements.append(gem_pos)
            relevant_values.append(gem_ttl)
        for opponent in __self__.opponents:
            relevant_elements.append(opponent)
            relevant_values.append(-abs(OPPONENT_PENALTY_TTL))
        # Add next unseen field, if no gem exists
        __self__.log(f'Gems: {len(__self__.gems)}, Unseen fields: {len(__self__.unseen_fields)}',log_level.INFO)
        if len(__self__.gems) == 0 and len(__self__.unseen_fields)>0:
            unseen_elements = __self__.__get_explorartion_fields()
            for x in unseen_elements:
                relevant_elements.append(x)
                relevant_values.append(10)
        # elif len(__self__.gems) == 0 and len(__self__.unseen_fields) == 0:
        patrol_elements = __self__.__get_patrol_fields()
        for x in patrol_elements:
            relevant_elements.append(x)
            relevant_values.append(1)
        __self__.log(f'Relevant elements: {relevant_elements}',log_level.INFO)
#        if __self__.field_changed or __self__.field is None:
            # with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            #     results = list(executor.map(__self__.build_field,relevant_elements,relevant_values))
            # __self__.field = np.sum(results)
        field = None
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
    def build_field(__self__,target:tuple[int,int],target_value:int=1,decay:float|None=DECAY_FACTOR):
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
        # Creates the potential field, with all known obstacles, unknown fields are handled as available fields for this
        __self__.log(f'Building field for target at {target} with value {target_value} and decay {decay}',log_level.DEBUG)
        map = np.full((__self__.height, __self__.width), 100, dtype=np.int8)
        q = deque()
        q.append((target[0],target[1], 0))
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
            q.append((x+1, y, nd))
            q.append((x-1, y, nd))
            q.append((x, y+1, nd))
            q.append((x, y-1, nd))
        if map[__self__.current_pos[1],__self__.current_pos[0]] == 100:
            __self__.void_fields.add(target)
            __self__.log(f'Target at {target} is unreachable, added to void fields',log_level.WARNING)
        if decay:
            map = target_value * decay ** map
        else:
            map = target_value * map
        return map
    def select_move(__self__)->str:
        '''
            gathers the four values around the bot, and its values. selects the field with the highest value as next move
        '''
        map = __self__.field
        bot_x = __self__.current_pos[0]
        bot_y = __self__.current_pos[1]
        directions = {}
        #Map is indexed [y,x] Select the possible next steps
        with open("debug_map.csv","w") as f:
            np.savetxt(f,map,delimiter=";")
        directions['W']=map[bot_y,max(bot_x-1,0)]
        directions['E']=map[bot_y,min(bot_x+1,__self__.width-1)]
        directions['N']=map[max(bot_y-1,0),bot_x]
        directions['S']=map[min(bot_y+1,__self__.height),bot_x]
        __self__.log(f'Bot position: {bot_x},{bot_y} {directions}')    
        print(max(directions,key=directions.get),flush=True)
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