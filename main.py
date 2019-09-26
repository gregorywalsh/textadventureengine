from classes import Game, Screen, Player

SCENE_DAT_FP = 'adv_cangranaria.yaml'
PARSE_DAT_FP = 'parsing.yaml'

screen = Screen(width=80)

player = Player(
    initial_scene=None,
    initial_inventory=set(),
    states=set(),
    visited_scene_names=set()
)

game = Game(
    game_data_fp=SCENE_DAT_FP,
    parsing_data_fp=PARSE_DAT_FP,
    screen=screen,
    player=player
)

screen.print(
    paragraphs=['', 'Welcome to', '', '', game.title, '', ''],
    alignment='centre',
    clear=True
)

screen.print(
    paragraphs=["To play the game, enter simple commands such as 'look', 'go north' or 'give apple to man'."],
    alignment='left',
    clear=False
)

input('\tPress "ENTER" to continue: ')

screen.print(
    paragraphs=[],
    alignment='left',
    clear=True
)

game.start()
