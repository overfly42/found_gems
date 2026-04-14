import random
random.seed(42)

from world import *
from common import *


class BaseSignalAnalyzer:
    def __init__(self, world: World):
        self.world = world

    def signal_level_to_distance(self, signal_level: float, signal_radius: float) -> float:
        if signal_level > 1:
            log(f'Signal level {signal_level} greater than 1, using maximum signal')
            signal_level = 1.0
        if signal_level <= 0:
            log(f'Signal level is 0, returning inf distance', log_level.INFO)
            return float('inf')
        return signal_radius * ((1 - signal_level) / signal_level) ** 0.5
    def signal_distance_to_signal_level(self, distance: float) -> float:
        # Distance formula
        # s = 1 / (1 + (d/r)²)
        # With d = distance, r = self.signal_radius, s = signal_level
        signal_level = 1 / (1 + (distance/self.world.signal_radius)**2)
        signal_level = np.round(signal_level,6)
        return signal_level
    def gaussian_distance_ring(self, robot_pos, target_distance, sigma, amplitude=1.0) -> np.ndarray:
        rows = self.world.height
        cols = self.world.width
        ry, rx = robot_pos
        y, x = np.ogrid[:rows, :cols]
        dist = np.sqrt((x - rx) ** 2 + (y - ry) ** 2)
        return amplitude * np.exp(-(dist - target_distance) ** 2 / (2 * sigma ** 2))

    def normalize(self, matrix: np.ndarray) -> np.ndarray:
        max_val = np.max(matrix)
        if max_val == 0 or np.isnan(max_val):
            return np.zeros_like(matrix)
        return matrix / max_val
    
    def analyze(self, *args, **kwargs) -> list[tuple[int, int]]:
        raise NotImplementedError('analyze method must be implemented by subclasses')

    def new_tick(self):
        pass
class GlobalSignalAnalyzer(BaseSignalAnalyzer):
    def __init__(self, world: World):
        super().__init__(world)
        self.signal_map = np.zeros_like(world.field, np.float64)
        self.first_signal = True

#    def analyze(self, signal_level: float, signal_radius: float) -> list[tuple[int, int]]:
    def analyze(self, data:dict) -> list[tuple[int, int]]:
        signal_level = data.get('signal_level', 0)
        signal_radius = data.get('signal_radius', 1.0)

        if signal_level <= 0:
            log('Discarding Global Signal analysis.')
            return []
        distances = [self.signal_level_to_distance(signal_level, signal_radius) / x for x in GAUS_RING_INTERVALS]
        signal_map = np.zeros_like(self.world.field, np.float64)
        for d in distances:
            signal_map += self.gaussian_distance_ring(self.world.bot_pos, d, sigma=SIGMA)
        signal_map = self.normalize(signal_map)

        if self.first_signal:
            self.signal_map = signal_map
            self.first_signal = False
        else:
            self.signal_map = SIGNAL_MAP_DECAY * self.signal_map + (1.0 - SIGNAL_MAP_DECAY) * signal_map
        self.signal_map = self.normalize(self.signal_map)
        self.signal_map[self.signal_map < SIGNAL_THRESHHOLD] = 0

        computed = {(x, y) for x, y in np.argwhere(self.signal_map > COPUTE_THREASHOLD)}
        computed.difference_update({(x, y) for x, y in np.argwhere(self.world.field == field_type.wall.value)})
        computed.difference_update(set(self.world.visible_fields.get(self.world.bot_pos, [])))
        return sorted(computed, key=lambda pos: euclidian_distance(pos, self.world.bot_pos))

class ChannelSignalAnalyzer(BaseSignalAnalyzer):
    def __init__(self, world: World):
        super().__init__(world)
        self.signal_memory: list[dict] = []

    def new_tick(self):
        self.signal_memory.append({})

    #def analyze(self, signals: list[float], signal_radius: float) -> list[tuple[int, int]]:
    def analyze(self, data:dict) -> list[tuple[int, int]]:
        
        log('Starting channel signal analysis')
        signals = data.get('signals', [])
        signal_radius = data.get('signal_radius', 1.0)
        if not isinstance(signals, list):
            log(f'Cannot analyze channel signal of type {type(signals)}')
            return []

        prev_mem = None if len(self.signal_memory) < 2 else self.signal_memory[-2]
        cur_mem = self.signal_memory[-1]
        cur_mem['channels'] = signals
        cur_mem['distribution'] = []
        cur_mem['distances'] = []
        cur_mem['targets'] = []

        for i, signal_level in enumerate(signals):
            last_signal_distribution = np.zeros_like(self.world.field, np.float64)
            if prev_mem is not None:
                last_signal_distribution = prev_mem['distribution'][i]
            if signal_level > 0:
                log(f'Channel {i} has signal strength {signal_level}')
            if signal_level <= 0:
                distance = float('inf')
                signal_distribution = np.zeros_like(self.world.field, np.float64)
            else:
                distance = self.signal_level_to_distance(signal_level, signal_radius)
                signal_distribution = self.gaussian_distance_ring(self.world.bot_pos, distance, sigma=SIGMA)
            cur_mem['distances'].append(distance)
            signal_distribution = SIGNAL_MAP_DECAY * last_signal_distribution + (1.0 - SIGNAL_MAP_DECAY) * signal_distribution
            signal_distribution = self.normalize(signal_distribution)
            cur_mem['distribution'].append(signal_distribution)
            max_val = np.max(signal_distribution)
            cur_mem['targets'].append({(x, y) for x, y in np.argwhere(signal_distribution > max_val * COPUTE_THREASHOLD)})

        statistics: dict[tuple[int, int], int] = {}
        for targets in cur_mem['targets']:
            for t in targets:
                statistics[t] = statistics.get(t, 0) + 1

        max_value = max(statistics.values()) if statistics else 1
        min_distance_index = np.argmin(cur_mem['distances']) if cur_mem['distances'] else 0
        computed = set(cur_mem['targets'][min_distance_index]) if cur_mem['targets'] else set()
        if max_value > 1:
            computed.update({k for k, v in statistics.items() if v == max_value})
            log('Using multiple channels for targets')

        walls = {(x, y) for x, y in np.argwhere(self.world.field == field_type.wall.value)}
        visible = set(self.world.visible_fields.get(self.world.bot_pos, []))
        computed.difference_update(walls)
        computed.difference_update(visible)
        return sorted(computed, key=lambda pos: euclidian_distance(pos, self.world.bot_pos))

class AntennaSignalAnalyzer(BaseSignalAnalyzer):
    DATA_KEY_ANTENNA = 'antenna_signals'
    DATA_KEY_GLOBAL = 'signal_level'
    SIGNAL_EPS = 0.005
    def analyze(self, data:dict) -> list[tuple[int, int]]:
        if self.DATA_KEY_ANTENNA not in data or self.DATA_KEY_GLOBAL not in data:
            log('Missing antenna signal data or global signal level, skipping analysis') 
            return []   
        #Collect all available singals    
        antenna_signals = data[self.DATA_KEY_ANTENNA]
        global_signal_level = data[self.DATA_KEY_GLOBAL]
        signals = []
        for x in antenna_signals:
            signals.append({'position':tuple(x['position']), 'signal':x['signal']})
        for x in signals:
            x['position'] = tuple([x['position'][1],x['position'][0]]) #switch x and y to match our coordinate system
        signals.append({'position':self.world.bot_pos, 'signal':global_signal_level})
        #Extend the signals by singal maps
        for x in signals:
            x['map'] = self.__build_signal_map(x['position'])
        #accumulate the signal maps and find positions that match the total signal level within an epsilon    
        sum_map  = np.zeros_like(self.world.field, np.float64)
        sum_signal = 0.0
        for x in signals:
            sum_map += x['map']
            sum_signal += x['signal']
            log(f'Signal from position {x["position"]} with level {x["signal"]} contributes max {np.max(x["map"])} to the sum map')
        if sum_signal <= 0:
            log('No valid signals found, skipping antenna signal analysis')
            return []
        log(f'Summed signal map has shape {sum_map.shape} and max value {np.max(sum_map)} with summed signal level {sum_signal} and {np.max(sum_map)} signal')
        results = {(x, y) for x, y in np.argwhere(
            (sum_map < (sum_signal + self.SIGNAL_EPS)) 
            &
            (sum_map > (sum_signal - self.SIGNAL_EPS))
            )}
        log(f'Found {len(results)} potential positions from antenna signal analysis')
        
        return sorted(results, key=lambda pos: euclidian_distance(pos, self.world.bot_pos))
    def __build_signal_map(self,pos:tuple[int, int])->np.ndarray:
            x0 = pos[1]
            y0 = pos[0]
            x = np.arange(self.world.width)
            y = np.arange(self.world.height)[:,None]
            map = np.sqrt(np.abs(x - x0)**2 + np.abs(y - y0)**2)
            # signal formula
            # s = 1 / (1 + (d/r)²)
            # With d = distance, r = __self__.signal_radius, s = signal_level
            map = 1.0 / (1.0 + (map / float(self.world.signal_radius))**2)
            return map

class MultiSourceAnalyzer(BaseSignalAnalyzer):
    DATA_KEY_ANTENNA = 'antenna_signals'
    DATA_KEY_GLOBAL = 'signal_level'
    DIST_EPS = 0.5
    SIGNAL_EPS = 0.1
    def __init__(self, world: World):
        super().__init__(world)
        self.dist_cache: dict[tuple[int, int], np.ndarray] = {}
        self.sig_cache: dict[tuple[int, int], np.ndarray] = {}
        self.history: set[tuple[int, int]] = set()

    def analyze(self, data:dict) -> list[tuple[int, int]]:
        max_gems = self.world.max_gems
        antenna_signals = data[self.DATA_KEY_ANTENNA]
        global_signal_level = data[self.DATA_KEY_GLOBAL]
        signals = []
        for x in antenna_signals:
            signals.append({'position':tuple(x['position']), 'signal':x['signal']})
        for x in signals:
            x['position'] = tuple([x['position'][1],x['position'][0]]) #switch x and y to match our coordinate system
        signals.append({'position':self.world.bot_pos, 'signal':global_signal_level})
        for x in signals:
            if x['position'] not in self.dist_cache:
                self.dist_cache[x['position']] = self.__build_distance_map(x['position'])
            x['dist_map'] = self.dist_cache[x['position']]
            x['signal_dist'] = self.signal_level_to_distance(x['signal'], self.world.signal_radius)
            if x['position'] not in self.sig_cache:
                self.sig_cache[x['position']] = 1.0 / (1.0 + (x['dist_map'] / float(self.world.signal_radius))**2)
            x['sig_map'] = self.sig_cache[x['position']]
        mask = np.ones_like(self.world.field, dtype=bool)
        #Mask all walls with 0
        mask[self.world.field == field_type.wall.value] = False
        #Mask all visible fields with 0
        visible = set(self.world.visible_fields.get(self.world.bot_pos, []))
        for v in visible:
            mask[v] = False
        for x in signals:
            mask[x['dist_map'] < x['signal_dist']-self.DIST_EPS] = False
        gem_masks = {1:{'mask':mask.copy()}}
        #First, check if one gem matches the signal perfectly, if so, return it immediately
        for x in signals:
            gem_masks[1]['mask'][x['dist_map'] > x['signal_dist']+self.DIST_EPS] = False
        base_coords = [tuple(x) for x in np.argwhere(gem_masks[1]['mask'])]
        #Select a gem randomly, and assume there is one more
        coords = [tuple(x) for x in np.argwhere(mask)]
        possible_possitions = self.history
        log(f'History has {len(possible_possitions)} positions')
        if coords:
            for _ in range( min(50 - len(possible_possitions),25)):
                possible_possitions.add(tuple(random.choice(coords)))
        for random_gem in possible_possitions:
            random_mask = np.ones_like(mask, dtype=bool)
            random_mask[self.world.field == field_type.wall.value] = False
            for s in signals:
                dist = euclidian_distance(random_gem, s['position'])
                signal_value = self.signal_distance_to_signal_level(dist)
                signal_rest = s['signal'] - signal_value
                random_mask[s['sig_map']<(signal_rest-self.SIGNAL_EPS)] = False
                random_mask[s['sig_map']>(signal_rest+self.SIGNAL_EPS)] = False
            coords_new = [tuple(x) for x in np.argwhere(random_mask)]
            if len(coords_new) == 0 or len(coords_new) > 5:
                continue
            coords_new.append(random_gem)
            log(f'Gem at {random_gem} with signal value {signal_value} and dist {dist}: {len(coords_new)} positions')
            base_coords.extend(coords_new)
    
        for k, v in gem_masks.items():
            v['count'] = np.sum(v['mask'])
            log(f'Gem mask for {k} gems has {v["count"]} potential positions')
            base_coords.extend([tuple(x) for x in np.argwhere(v['mask'])])
        #####################################################
        # #Get all coordinates of the remaining fields
        # coords = [tuple(x) for x in np.argwhere(mask)]
        # log(f'Found {len(coords)} potential positions from multi-source signal analysis')
        new_coords = set()
        self.history = new_coords
        for x in base_coords:
            for _,d in DIRS.items():
                neighbor = (x[0]+d[0], x[1]+d[1])
                if neighbor in coords:
                    new_coords.add(neighbor)
                new_coords.add(x)
        return list(new_coords)
    def __build_distance_map(self,pos:tuple[int, int])->np.ndarray:
            x0 = pos[1]
            y0 = pos[0]
            x = np.arange(self.world.width)
            y = np.arange(self.world.height)[:,None]
            map = np.sqrt(np.abs(x - x0)**2 + np.abs(y - y0)**2)
            return map    
