#!/usr/bin/env python3
import sys, json, random

DEBUG = False

random.seed(1)
class gem_searcher:
    def __init__(__self__):
        __self__.config = {}
        __self__.width = 0
        __self__.height = 0
        __self__.first_tick = True
    def log(__self__,message):
        if DEBUG:
            print(message,file=sys.stderr,flush=True)

    def analyse_json(__self__,data):
        if __self__.first_tick:
            __self__.log('First Tick')
            __self__.config = data.get("config", {})
            __self__.width = __self__.config.get("width")
            __self__.height = __self__.config.get("height")
            print(f"Overflys bot searching for gems on a {__self__.width}x{__self__.height} map",
                file=sys.stderr, flush=True)
            __self__.first_tick = False
        else:
            __self__.log('Subsequent Tick')
        my_pos = {'bot':data['bot'],"visible_gems":data.get("visible_gems",None)}
        if not my_pos["visible_gems"]:
            my_pos["visible_gems"] = [
                {'position':[__self__.width//2,__self__.height//2],
                'ttl':1}
            ]
        gems = [{
        'x_gem':  x['position'][0],
        'y_gem': x['position'][1]
        } for x in my_pos["visible_gems"]
        ]
        x_bot = my_pos["bot"][0]
        y_bot = my_pos["bot"][1]
        for x in gems:
            x['distance'] = abs(x_bot - x['x_gem']) +abs(y_bot-x['y_gem']) 
        gems.sort(key=lambda x:x['distance'])
        return {'x':x_bot,'y':y_bot}, gems,my_pos
    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line)
            bot, gems, meta_data = __self__.analyse_json(data)
            x_gem = gems[0]['x_gem']
            y_gem = gems[0]['y_gem']
            if x_gem != bot['x']:
                move = 'E' if x_gem > bot['x'] else 'W'
            elif y_gem != bot['y']:
                move = 'S' if y_gem > bot['y'] else 'N'
            else:
                move = random.choice(["N", "S", "E", "W"])
            print(move, flush=True)
            meta_data['selected'] = move
            __self__.log(json.dumps(meta_data))
            first_tick = False
if __name__ == "__main__":
    gem_searcher().main()