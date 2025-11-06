#!/usr/bin/env python3
import sys, json, random

DEBUG = False

random.seed(1)
first_tick = True

def log(message):
    if DEBUG:
        print(json.dumps(my_pos),file=sys.stderr,flush=True)


for line in sys.stdin:
    data = json.loads(line)
    if first_tick:
        config = data.get("config", {})
        width = config.get("width")
        height = config.get("height")
        print(f"Random walker (Python) launching on a {width}x{height} map",
              file=sys.stderr, flush=True)
    
    my_pos = {'bot':data['bot'],"visible_gems":data.get("visible_gems",None)}
    if not my_pos["visible_gems"]:
        my_pos["visible_gems"] = [
            {'position':[width//2,height//2],
            'ttl':1}
        ]
    x_gem = my_pos["visible_gems"][0]['position'][0]
    y_gem = my_pos["visible_gems"][0]['position'][1]
    x_bot = my_pos["bot"][0]
    y_bot = my_pos["bot"][1]
    if x_gem != x_bot:
        move = 'E' if x_gem > x_bot else 'W'
    elif y_gem != y_bot:
        move = 'S' if y_gem > y_bot else 'N'
    else:
        move = random.choice(["N", "S", "E", "W"])
    print(move, flush=True)
    my_pos['selected'] = move
    log(json.dumps(my_pos))
    first_tick = False
