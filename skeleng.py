"""
This module contains the necessary classes required to run a Skeletronica Adventure File (SAF)
and an associated input parsing file (IPF).
"""

import os
import yaml
from re import search as regex_search
from textwrap import wrap, fill, indent


class Game:

    """
    Main object required to play the game

    Args:
        game_data_fp (str): file path to a Skeletronica adventure file (SAF)
        parsing_data_fp (str)): file path to an input parsing file (IPF)
        printer (Printer): a printer object
        player (Player): a player object

    Attributes:
        title (str): The title of the game
        player(Player): The player of the game
        input_parser(InputParser): The game's input parser
        printer(Printer): The game's printer
    """

    def __init__(self, game_data_fp, parsing_data_fp, printer, player):
        metadata, self.scenes = Game._load_game_data(game_data_fp)
        self.title = metadata['title']
        self.player = player
        self.input_parser = InputParser.load_parser(parsing_data_fp)
        self.printer = printer
        self._first_scene = metadata['first_scene']
        self._first_action = metadata['first_action']
        self._in_progress = True

    def start(self):
        """
        Initialises the game by printing the title screen and beginning the input/action loop

        Returns:
            None
        """

        self.printer.print(
            paragraphs=['', 'Welcome to', '', '', self.title, '', ''],
            alignment='centre',
            clear=True
        )
        self.printer.print(
            paragraphs=["To play the game, enter simple commands such as 'look', 'go north' or 'give apple to man'."],
            alignment='left',
            clear=False
        )
        input('\tPress "ENTER" to continue: ')
        self.printer.print(
            paragraphs=[],
            alignment='left',
            clear=True
        )
        self.player.current_scene = self.scenes[self._first_scene]
        self.play(self._first_action)
        while self._in_progress:
            self.play()

    def play(self, override_input=None):
        player_input = override_input if override_input else self.input_parser.get_player_input()
        outcome = self._get_matching_outcome(player_input)
        if outcome:
            self._process_outcome(outcome)
        else:
            self.printer.print(
                paragraphs=['You cannot do that now.'],
                alignment='left',
                clear=False
            )

    def _get_matching_outcome(self, player_input):
        pattern = self.input_parser.get_pattern(player_input)

        matched_outcome = None
        for action in self.player.current_scene.actions:
            if regex_search('_no_match', action.name):  # Check for a default override
                matched_outcomes = [outcome for outcome in action.outcomes if outcome.check_reqs(self)]
                matched_outcome = matched_outcomes[0] if matched_outcomes else None
            if regex_search(pattern, action.name):
                matched_outcomes = [outcome for outcome in action.outcomes if outcome.check_reqs(self)]
                matched_outcome = matched_outcomes[0] if matched_outcomes else None
                break
        return matched_outcome

    def _process_outcome(self, outcome):
        self.printer.print(
            paragraphs=outcome.text,
            alignment='left',
            clear=outcome.clear,
        )
        self._update_states(outcome)

    def _update_states(self, outcome):
        for state_mutator in outcome.mutators:
            state_mutator.mutator_func(self)

    @staticmethod
    def _load_game_data(game_data_fp):
        yaml.add_constructor('!Scenes', Scene.scenes_constructor, Loader=yaml.SafeLoader)
        with open(game_data_fp, 'r') as f:
            game_data = list(yaml.safe_load_all(stream=f))
        return game_data


class InputParser:

    def __init__(self, small_words, translations):
        self.small_words = small_words
        self.translations = translations

    def get_pattern(self, player_input):
        important_words = [word for word in player_input.split(' ') if word not in self.small_words]
        translated_words = [self.translations[word] if word in self.translations else word for word in important_words]
        return '^{words}$'.format(words=' '.join(translated_words))

    @staticmethod
    def load_parser(parsing_data_fp):
        yaml.add_constructor('!Parsing', InputParser.yaml_constructor, Loader=yaml.SafeLoader)
        with open(parsing_data_fp, 'r') as f:
            parser = yaml.safe_load(stream=f)
        return parser

    @staticmethod
    def get_player_input():
        # TODO add some checks in here
        return input('\t> ').lower()

    @staticmethod
    def yaml_constructor(loader, node):
        data = loader.construct_mapping(node, deep=True)
        small_words = data['small_words']
        translations = data['translations']
        return InputParser(small_words, translations)


class Scene:

    def __init__(self, name):
        self.name = name
        self.actions = []

    def add_action(self, action):
        self.actions.append(action)

    @staticmethod
    def scenes_constructor(loader, node):
        data = loader.construct_mapping(node, deep=True)
        scenes = {scene_name: Scene(scene_name) for scene_name in data.keys()}
        for scene_name, scene_data in data.items():
            for action_name, outcomes_data in scene_data['actions'].items():
                scenes[scene_name].add_action(Action.constructor(action_name, outcomes_data))
        return scenes


class Action:

    def __init__(self, name, outcomes):
        self.name = name
        self.outcomes = outcomes

    def check_outcomes(self, game):
        # TODO
        pass

    @staticmethod
    def constructor(name, outcomes_data):
        outcomes = []
        for outcome_data in outcomes_data:
            outcomes.append(Outcome.constructor(outcome_data))
        return Action(name, outcomes)


class Outcome:

    def __init__(self, requirements, mutators, text, clear):
        self.requirements = requirements
        self.mutators = mutators
        self.text = text
        self.clear = clear

    def check_reqs(self, game):
        return all(requirement.check(game) for requirement in self.requirements)

    @staticmethod
    def constructor(outcome_data):

        requirements = []
        if 'reqs' in outcome_data:
            for req_type, targets in outcome_data['reqs'].items():
                for target in targets:
                    requirements.append(Requirement.constructor(req_type, target))

        clear = False
        mutators = []
        if 'mutators' in outcome_data:
            for mutator_type, targets in outcome_data['mutators'].items():
                if mutator_type == 'player_move_to':
                    clear = True
                for target in targets:
                    mutators.append(StateMutator.constructor(mutator_type, target))

        text = None
        if 'text' in outcome_data:
            text = outcome_data['text']
            text = [text] if isinstance(text, str) else text

        return Outcome(requirements, mutators, text, clear)


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

        if req_type == 'has_item':
            def check_func(game):
                return target in game.player.inventory
        elif req_type == 'not_has_item':
            def check_func(game):
                return target not in game.player.inventory
        elif req_type == 'has_state':
            def check_func(game):
                return target in game.player.states
        elif req_type == 'not_has_state':
            def check_func(game):
                return target not in game.player.states
        elif req_type == 'has_visited':
            def check_func(game):
                return target in game.player.visited_scene_names
        elif req_type == 'not_has_visited':
            def check_func(game):
                return target not in game.player.visited_scene_names
        else:
            raise ValueError

        return check_func


class StateMutator:

    def __init__(self, mutator_func):
        self.mutator_func = mutator_func

    @staticmethod
    def constructor(mutator_type, target):
        return StateMutator(mutator_func=StateMutator.make_mutator_func(mutator_type, target))

    @staticmethod
    def make_mutator_func(mutator_type, target):

        if mutator_type == 'player_move_to':
            def mutator_func(game):
                game.player.current_scene = game.scenes[target]
                game.play('_arrive')
        elif mutator_type == 'player_arrive':
            def mutator_func(game):
                game.player.visited_scene_names.add(game.scenes[target].name)
        elif mutator_type == 'add_item':
            def mutator_func(game):
                game.player.inventory.add(target)
        elif mutator_type == 'remove_item':
            def mutator_func(game):
                game.player.inventory.remove(target)
        elif mutator_type == 'add_state':
            def mutator_func(game):
                game.player.states.add(target)
        elif mutator_type == 'remove_state':
            def mutator_func(game):
                game.player.states.remove(target)
        elif mutator_type == 'game_end':
            def mutator_func(game):
                game._in_progress = False
        else:
            raise ValueError('"{}" is not a valid mutator type'.format(mutator_type))
        return mutator_func


class Printer:

    def __init__(self, width):
        self.width = width

    def print(self, paragraphs, alignment, clear):
        if clear:
            Printer.clear()
            print()
        for paragraph in paragraphs:
            if alignment == 'left':
                print(indent(fill(paragraph, self.width), '\t'), '\n')
            elif alignment == 'centre':
                print(*[indent(str.center(x, self.width), '\t') for x in wrap(paragraph)])

    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')


class Player:

    def __init__(self, initial_scene, initial_inventory, states, visited_scene_names):
        self.current_scene = initial_scene
        self.inventory = initial_inventory
        self.states = states
        self.visited_scene_names = visited_scene_names
