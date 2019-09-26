import os
from yaml import add_constructor as add_yaml_constructor, load
from re import search as regex_search
from textwrap import wrap, fill, indent


class Game:

    def __init__(self, scene_data_fp, parsing_data_fp, screen, player):
        self.scenes = self._load_scene_data(scene_data_fp)
        self.parser = Parser.load_parser(parsing_data_fp)
        self.screen = screen
        self.player = player
        self.in_progress = True

    def start(self, scene):
        self.player.current_scene = self.scenes[scene]
        self.do('_arrive')
        while self.in_progress:
            self.do()

    def do(self, game_input=None):
        player_input = game_input if game_input else self._get_player_input()
        option = self._get_matching_option(player_input)
        if option:
            self._execute_option(option)
        else:
            self.screen.print(
                paragraphs=['You cannot do that.'],
                alignment='left',
                clear=False
            )

    def _load_scene_data(self, scene_data_fp):
        add_yaml_constructor(u'!Scenes', Scene.dict_constructor)
        with open(scene_data_fp, 'r') as f:
            scenes = load(f)
        return scenes

    def _get_player_input(self):
        # TODO add some checks in here
        return input('\t> ').lower()

    def _get_matching_option(self, player_input):
        pattern = self.parser.get_pattern(player_input)

        matched_option = None
        for action in self.player.current_scene.actions:
            if regex_search('_no_match', action.name):  # Check for a default override
                matched_options = [option for option in action.options if option.check_reqs(self)]
                matched_option = matched_options[0] if matched_options else None
            if regex_search(pattern, action.name):
                matched_options = [option for option in action.options if option.check_reqs(self)]
                matched_option = matched_options[0] if matched_options else None
                break
        return matched_option

    def _execute_option(self, option):
        self.screen.print(
            paragraphs=option.text,
            alignment='left',
            clear=option.clear,
        )
        self._update_states(option)

    def _update_states(self, option):
        for state_mutator in option.state_mutators:
            state_mutator.mutator_func(self)


class Parser:

    def __init__(self, small_words, translations):
        self.small_words = small_words
        self.translations = translations

    def get_pattern(self, player_input):
        important_words = [word for word in player_input.split(' ') if word not in self.small_words]
        translated_words = [self.translations[word] if word in self.translations else word for word in important_words]
        return '^{words}$'.format(words=' '.join(translated_words))

    @staticmethod
    def load_parser(parsing_data_fp):
        add_yaml_constructor(u'!Parsing', Parser.constructor)
        with open(parsing_data_fp, 'r') as f:
            parser = load(f)
        return parser

    @staticmethod
    def constructor(loader, node):
        data = loader.construct_mapping(node, deep=True)
        small_words = data['small_words']
        translations = data['translations']
        return Parser(small_words, translations)


class Scene:

    def __init__(self, name):
        self.name = name
        self.actions = []

    def add_action(self, action):
        self.actions.append(action)

    @staticmethod
    def dict_constructor(loader, node):
        data = loader.construct_mapping(node, deep=True)
        scenes = {}
        for scene_name in data.keys():
            scenes[scene_name] = Scene(scene_name)
        for scene_name, scene_data in data.items():
            for action_name, options_data in scene_data['actions'].items():
                scenes[scene_name].add_action(Action.constructor(action_name, options_data))
        return scenes


class Action:

    def __init__(self, name, options):
        self.name = name
        self.options = options

    def check_options(self, game):
        pass

    @staticmethod
    def constructor(name, options_data):
        options = []
        for option_data in options_data:
            options.append(Option.constructor(option_data))
        return Action(name, options)


class Option:

    def __init__(self, requirements, state_mutators, text, clear):
        self.requirements = requirements
        self.state_mutators = state_mutators
        self.text = text
        self.clear = clear

    def check_reqs(self, game):
        return all(requirement.check(game) for requirement in self.requirements)

    @staticmethod
    def constructor(option_data):

        reqirements = []
        if 'reqs' in option_data:
            for  req_type, targets in option_data['reqs'].items():
                for target in targets:
                    reqirements.append(Requirement.constructor(req_type, target))

        clear = False
        state_mutators = []
        if 'state_mutators' in option_data:
            for mutator_type, targets in option_data['state_mutators'].items():
                if mutator_type == 'player_leave':
                    clear = True
                for target in targets:
                    state_mutators.append(StateMutator.constructor(mutator_type, target))

        text = None
        if 'text' in option_data:
            text = option_data['text']
            text = [text] if isinstance(text, str) else text

        return Option(reqirements, state_mutators, text, clear)


class Requirement:

    def __init__(self, test_func):
        self.test_func = test_func

    def check(self, game):
        return self.test_func(game)

    @staticmethod
    def constructor(req_type, target):
        return Requirement(test_func=Requirement.make_check_fnc(req_type, target))

    @staticmethod
    def make_check_fnc(req_type, target):

        if req_type == 'player_has':
            check_func = lambda game: target in game.player.inventory
        elif req_type == 'not_player_has':
            check_func = lambda game: target not in game.player.inventory
        elif req_type == 'player_visited':
            check_func = lambda game: target in game.player.visited_scene_names
        elif req_type == 'not_player_visited':
            check_func = lambda game: target not in game.player.visited_scene_names
        else:
            raise(ValueError)

        return check_func


class StateMutator:

    def __init__(self, mutator_func):
        self.mutator_func = mutator_func

    @staticmethod
    def constructor(mutator_type, target):
        return StateMutator(mutator_func=StateMutator.make_mutator_func(mutator_type, target))

    @staticmethod
    def make_mutator_func(mutator_type, target):

        if mutator_type == 'player_leave':
            def mutator_func(game):
                game.player.current_scene = game.scenes[target]
                game.do('_arrive')
        elif mutator_type == 'player_arrive':
            def mutator_func(game):
                game.player.visited_scene_names.add(game.scenes[target].name)
        elif mutator_type == 'add_to_player':
            def mutator_func(game):
                game.player.inventory.add(target)
        elif mutator_type == 'remove_from_player':
            def mutator_func(game):
                game.player.inventory.remove(target)
        else:
            raise ValueError('"{}" is not a valid mutator type'.format(mutator_type))
        return mutator_func


class Screen:

    def __init__(self, width):
        self.width = width

    def print(self, paragraphs, alignment, clear):
        if clear:
            Screen.clear()
            print()
        for paragraphs in paragraphs:
            if alignment == 'left':
                print(indent(fill(paragraphs, self.width), '\t'))
            elif alignment == 'centre':
                print(*[indent(str.center(x, self.width), '\t') for x in wrap(paragraphs)])

    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')


class Player:

    def __init__(self, initial_scene, initial_inventory, visited_scene_names):
        self.current_scene = initial_scene
        self.inventory = initial_inventory
        self.visited_scene_names = visited_scene_names
