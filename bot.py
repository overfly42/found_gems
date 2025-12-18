#!/usr/bin/env python3
import sys, json, random
from collections import deque
import numpy as np
from uuid import uuid4


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

if __name__ == "__main__":
    gem_searcher().main()
    # bot = gem_searcher()
    # bot.width = 10
    # bot.height = 10
    # bot.known_walls.update([(3,4),(3,5),(3,6)]) 
    # print(bot.build_single_map({'x_gem':5,'y_gem':5,'ttl':5}))