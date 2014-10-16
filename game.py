from __future__ import with_statement
import libtcodpy as tcod
import random

map_char_data = {
    '#': {
        'character': '#',
        'color': tcod.Color(80, 80, 80),
        'background': tcod.Color(40, 40, 40),
        'transparent': False,
        'walkable': False
    },
    ' ': {
        'character': ' ',
        'color': tcod.Color(255, 255, 255),
        'background': tcod.Color(40, 40, 40),
        'transparent': True,
        'walkable': True
    },
    'X': {
        'character': '#',
        'color': tcod.Color(114,255,114),
        'background': tcod.Color(40, 40, 40),
        'transparent': False,
        'walkable': False
    }
}

class Tile(object):
    def __init__(self, character, color, fog_color=None, background=None,
                 fog_background=None, transparent=True, walkable=True):
        self.character = character
        self.color = color
        self.background = background
        self.transparent = transparent
        self.walkable = walkable
        self.explored = False
        self.fog_color = self.color * 0.3
        self.fog_background = self.background * 0.3

    def draw_at(self, console, x, y, visible):
        if visible:
            self.explored = True
            tcod.console_put_char_ex(console, x, y, self.character, self.color,
                                     self.background)
        elif self.explored:
            tcod.console_put_char_ex(console, x, y, self.character,
                                     self.fog_color, self.fog_background)
        else:
            tcod.console_put_char(console, x, y, ' ', tcod.BKGND_NONE)



class Object(Tile):
    def __init__(self, x, y, game, **kwargs):
        super(Object, self).__init__(**kwargs)
        self.x = x
        self.y = y
        self.game = game

    def draw(self):
        visible = self.game.fov.is_visible(self.x, self.y)
        self.explored = False
        self.draw_at(self.game.console, self.x, self.y, visible)

    def move(self, dx, dy):
        if not self.game.fov.is_walkable(self.x + dx, self.y + dy):
            return False
        was_visible = self.game.fov.is_visible(self.x, self.y)
        self.game.fov.clear_tile(self.x, self.y)
        self.x += dx
        self.y += dy
        self.game.fov.set_tile(self.x, self.y, self)
        is_visible = self.game.fov.is_visible(self.x, self.y)
        if was_visible or is_visible:
            self.game.fov.dirty = True
        return True

    def clear(self):
        tcod.console_put_char(self.game.console, self.x, self.y, ' ')

    def process(self, fov):
        pass

class NPC(Object):
    def __init__(self, *args, **kwargs):
        super(NPC, self).__init__(*args, **kwargs)
        self.walkable = False
        self.movement = 0.2
        self.points = 0
        self.seen = 0
        self.orig_color = self.color

    def process(self, game):
        visible =self.game.fov.is_visible(self.x, self.y)
        moved = False

        if visible:
            self.seen += 1
            self.color = tcod.color_lerp(tcod.dark_gray, self.orig_color,
                                         (self.seen % 50) / 100.0)
            if self.seen % 50 == 0:
                self.game.duplicate(self)

            if self.seen == 200:
                self.character = 'o'
                self.movement = 0.4

            elif self.seen == 400:
                self.character = 'O'
                self.movement = 0.6

            path = tcod.path_new_using_map(self.game.fov.fov, 1.0)
            tcod.path_compute(path, self.x, self.y, self.game.player.x,
                              self.game.player.y)

            if tcod.path_size(path) > 2:
                self.points += self.movement
                if self.points >= 1:
                    self.points -= 1
                    x, y = tcod.path_get(path, 1)
                    self.move(x - self.x, y - self.y)
                    moved = True
            tcod.path_delete(path)

        if not moved:
            self.points += self.movement
            if self.points >= 1:
                self.points -= 1
                movement = [
                    (0, 0),
                    (0, 1),
                    (0, -1),
                    (1, 0),
                    (-1, 0),
                    (1, 1),
                    (-1, -1),
                    (-1, 1),
                    (1, -1)
                ]
                self.move(*random.choice(movement))

        return True


class Map(object):
    def __init__(self, game, data, char_data):
        self.tiles = []
        self.game = game
        for y, row in enumerate(data):
            self.tiles.append([])
            for x, char in enumerate(row):
                properties = char_data[char]
                self.tiles[y].append(Tile(**properties))

        self.height = len(self.tiles)
        self.width = len(self.tiles[0])

    @classmethod
    def from_file(cls, game, file, char_data):
        with open(file, 'r') as fh:
            return cls(game, [l.strip() for l in fh.readlines()], char_data)


    def draw(self):
        for x, y, tile in self:
            visible = self.game.fov.is_visible(x, y)
            tile.draw_at(self.game.console, x, y, visible)

    def __iter__(self):
        for y, row, in enumerate(self.tiles):
            for x, tile in enumerate(row):
                yield x, y, tile


class Fov(object):
    def __init__(self, width, height, game, radius=10):
        self.fov = tcod.map_new(width, height)
        self._radius = radius
        self.game = game
        self.dirty = True
        self.set_map()

    def is_visible(self, x, y):
        return tcod.map_is_in_fov(self.fov, x, y)

    def is_walkable(self, x, y):
        return tcod.map_is_walkable(self.fov, x, y)

    def get_radius(self):
        return self._radius

    def set_radius(self, radius):
        self.dirty = True
        self._radius = radius

    radius = property(get_radius, set_radius)

    def set_map(self):
        for x, y, tile in self.game.map:
            self.set_tile(x, y, tile)

    def clear_tile(self, x, y):
        tcod.map_set_properties(self.fov, x, y, True, True)

    def set_tile(self, x, y, tile):
        tcod.map_set_properties(self.fov, x, y, tile.transparent, tile.walkable)

    def recompute(self):
        tcod.map_compute_fov(self.fov, self.game.player.x, self.game.player.y,
                             self._radius, True, tcod.FOV_SHADOW)
        self.dirty = False


class Game(object):
    def __init__(self, width, height, map_file):
        tcod.console_set_custom_font(
            'terminal8x8_gs_tc.png',
            tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD
        )
        tcod.console_init_root(width, height, 'test', False, tcod.RENDERER_GLSL)
        tcod.sys_set_fps(20)
        tcod.console_set_keyboard_repeat(300, 10)

        self.width = width
        self.height = height
        self.exit = False
        self.map = Map.from_file(self, map_file, map_char_data)
        self.console = tcod.console_new(self.map.width, self.map.height)
        self.player = Object(
            self.map.width / 2, self.map.height / 2, character='@', game=self,
            color=tcod.green, background=tcod.Color(40, 40, 40), walkable=True
        )
        self.fov = Fov(self.map.width, self.map.height, game=self, radius=30)
        self.objects = [self.player]
        self.step = 0

        self.fov.recompute()
        for i in range(10):
            x, y = random.randrange(self.map.width), random.randrange(self.map.height)
            if self.fov.is_walkable(x, y):
                self.spawn_npc(x, y)

        self.fov.dirty = True
        self.keys = {
            tcod.KEY_UP: self.action_north,
            tcod.KEY_DOWN: self.action_south,
            tcod.KEY_RIGHT: self.action_east,
            tcod.KEY_LEFT: self.action_west,
            tcod.KEY_ESCAPE: self.action_exit,
            tcod.KEY_KP8: self.action_north,
            tcod.KEY_KP2: self.action_south,
            tcod.KEY_KP6: self.action_east,
            tcod.KEY_KP4: self.action_west,
            tcod.KEY_KP7: self.action_northwest,
            tcod.KEY_KP1: self.action_southwest,
            tcod.KEY_KP9: self.action_northeast,
            tcod.KEY_KP3: self.action_southeast,
            tcod.KEY_KP5: self.action_pass,
        }

    def duplicate(self, obj):
        positions =  [
            (0, 1),
            (0, -1),
            (1, 0),
            (-1, 0),
            (1, 1),
            (-1, -1),
            (-1, 1),
            (1, -1)
        ]
        for x, y in positions:
            if self.fov.is_walkable(obj.x + x, obj.y + y):
                self.spawn_npc(obj.x, obj.y)
                break


    def spawn_npc(self, x, y):
        self.objects.insert(0, NPC(x, y, game=self, character='.',
                                   color=tcod.red,
                                   background=tcod.Color(40, 40, 40)))

    def handle_keys(self, key):
        if key.vk not in self.keys:
            return False
        return self.keys[key.vk](key)

    def move_player(self, dx, dy):
        return self.player.move(dx, dy)

    def action_north(self, key):
        return self.move_player(0, -1)

    def action_south(self, key):
        return self.move_player(0, 1)

    def action_east(self, key):
        return self.move_player(1, 0)

    def action_west(self, key):
        return self.move_player(-1, 0)

    def action_northwest(self, key):
        return self.move_player(-1, -1)

    def action_southwest(self, key):
        return self.move_player(-1, 1)

    def action_northeast(self, key):
        return self.move_player(1, -1)

    def action_southeast(self, key):
        return self.move_player(1, 1)

    def action_pass(self, key):
        return True

    def action_exit(self, key):
        self.exit = True
        return True

    def process(self):
        print 'Enemies:', len(self.objects) - 1
        if self.fov.dirty:
            self.fov.recompute()
            self.map.draw()

        for obj in self.objects:
            obj.draw()

        screen_x1 = self.player.x - (self.width / 2)
        screen_y1 = self.player.y - (self.height / 2)
        screen_x2 = screen_x1 + self.width
        screen_y2 = screen_y1 + self.height

        if screen_x2 > self.map.width:
            screen_x1 = self.map.width - self.width

        if screen_y2 > self.map.height:
            screen_y1 = self.map.height - self.height

        if screen_x1 < 0:
            screen_x1 = 0

        if screen_y1 < 0:
            screen_y1 = 0

        tcod.console_blit(self.console, screen_x1, screen_y1, self.width, self.height, 0, 0, 0)
        tcod.console_flush()

        handled = False
        while not handled:
            key = tcod.console_wait_for_keypress(True)
            handled = self.handle_keys(key)

        for obj in self.objects:
            obj.process(self)
            obj.clear()