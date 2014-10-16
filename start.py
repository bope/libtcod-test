import libtcodpy as tcod
from game import Game


if __name__ == '__main__':
    game = Game(160, 100, 'map.dat')

    while not game.exit:
        game.process()
