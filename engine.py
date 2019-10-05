# Created by Gregory Walsh

"""
This module contains the necessary classes required to run a YAML Adventure File (YAF)
and an associated Input Parsing File (IPF).
"""

import os
import yaml
from pickle import dump
from textwrap import wrap, fill, indent

OS_NAME = os.name
if os.name == 'nt':
    import msvcrt


class Game:
    """
    Use this class to run a new game from an Adventure File (SAF).

    Args:
        game_data_fp (str): file path to a SAF
        input_parser (InputParser): an InputParser object for parsing player inputs
        shell (Shell): a Shell for displaying the game and getting inputs
        player (Player): a player object with state info such as inventory, location, etc.

    Attributes:
        player (Player): The player of the game
        shell (Shell): The Game's shell. Can be used to print messages
    """

    def __init__(self, game_data_fp, input_parser, shell, player):
        self.player = player
        self.input_parser = input_parser
        self._shell = shell
        self._metadata, self.scenes = Game._load_game_data(self, game_data_fp)
        self._in_progress = True

    def start(self):
        """
        Initialises the Game by printing the title screen and beginning the input/actions loop.

        Returns:
            None
        """
        self._shell.clear()
        self._shell.print(
            paragraphs=['Welcome to', self._metadata['title']],
            alignment='centre'
        )
        self._shell.print(
            paragraphs=['To play the game, enter simple commands such as "look", "go north" or "give apple to man".'],
            alignment='left'
        )
        self._shell.pause()
        self._shell.clear()
        self.player.current_scene = self.scenes[self._metadata['first_scene']]
        self.play(override_key=self._metadata['first_action_key'])
        while self._in_progress:
            self.play()

    def play(self, override_key=None):
        """
        Performs a single game step:
            - request input
            - find matching actions
            - determine outcome by requirements
            - execute associated mutators

        If override_key given, player not asked for input

        Args:
            override_key (:obj:`str`, optional): Replaces player input

        Returns:
            None
        """
        input_action_key = override_key or self.input_parser.make_action_key(text_input=self._shell.get_player_input())
        action = self._match_action(input_action_key=input_action_key)
        if action:
            outcome = self._match_outcome(action)
            if outcome:
                self._process_outcome(outcome=outcome)
            else:
                self._shell.print(
                    paragraphs=['You cannot do that now.'],
                    alignment='left'
                )
        else:
            self._shell.print(
                paragraphs=['You cannot do that now.'],
                alignment='left'
            )

    def _match_action(self, input_action_key):
        """ Given an input, returns first matching actions. Falls back to default '_no_match' action if available."""
        get_action = self.player.current_scene.actions.get
        return get_action(input_action_key) or get_action(frozenset(['_no_match']))

    def _match_outcome(self, action):
        """ Given an actions, returns the first possible matching outcome by checking requirements against
            the player's state.
        """
        matched_outcomes = [outcome for outcome in action.outcomes if outcome.check_requirements(self.player)]
        return matched_outcomes[0] if matched_outcomes else None

    def _process_outcome(self, outcome):
        """Processes outcome, e.g. change player location, and updates shell"""
        player_original_scene = self.player.current_scene
        self._update_states(mutators=outcome.mutators)
        if player_original_scene != self.player.current_scene:
            self._shell.clear()
            self._shell.print(
                paragraphs=outcome.text,
                alignment='left'
            )
            self.play(override_key=frozenset(['_arrive']))
        else:
            self._shell.print(
                paragraphs=outcome.text,
                alignment='left'
            )

    def _update_states(self, mutators):
        """Given an outcome, modifies player states e.g. location, inventory."""
        for state_mutator in mutators:
            state_mutator.mutator_func(self)

    def _load_game_data(self, game_data_fp):
        """Loads a YAML Adventure File (game metadata and a list of scenes) from disk"""
        loader = yaml.SafeLoader
        yaml.add_constructor(tag='!Metadata', constructor=Game._pyyaml_meta_data_constructor, Loader=loader)
        yaml.add_constructor(tag='!Scene', constructor=_Scene.pyyaml_constructor, Loader=loader)
        action_constructor = _Action.make_pyyaml_constructor(input_parser=self.input_parser)
        yaml.add_constructor(tag='!Action', constructor=action_constructor, Loader=loader)
        yaml.add_constructor(tag='!Outcome', constructor=_Outcome.pyyaml_constructor, Loader=loader)
        yaml.add_constructor(tag='!Mutator', constructor=_Mutator.pyyaml_constructor, Loader=loader)
        yaml.add_constructor(tag='!Requirement', constructor=_Requirement.pyyaml_constructor, Loader=loader)
        with open(game_data_fp, 'r') as f:
            meta_data, scenes = list(yaml.safe_load_all(stream=f))
        return meta_data, {scene.key: scene for scene in scenes}

    @staticmethod
    def _pyyaml_meta_data_constructor(loader, node):
        """defines a constructor for a PyYAML loader"""
        data = loader.construct_mapping(node, deep=True)
        first_action_key = frozenset([data['first_action']])
        return {'title': data['title'], 'first_scene': data['first_scene'], 'first_action_key': first_action_key}


class InputParser:
    """
    Converts player inputs into actions-keys that can then be used to find matching actions for a scene.

    Args:
        stop_words (iter of str): short words that should be excluded when creating actions-keys
        synonyms (dict): mappings from synonyms (take, grab) to a canonical version (get)
    """

    def __init__(self, stop_words, synonyms):
        self._stop_words = stop_words
        self._synonyms = synonyms

    def make_action_key(self, text_input):
        """
        Converts a player input to an actions-key by removing stopwords and converting synonyms to their
        canonical versions.

        Returns:
            An actions-key (frozenset)
        """
        important_words = [w for w in text_input.split(' ') if w not in self._stop_words]
        translated_action_key = frozenset(self._synonyms[w] if w in self._synonyms else w for w in important_words)
        return translated_action_key

    @classmethod
    def construct_from_yaml(cls, parsing_data_fp):
        """
        Constructs an InputParser from an appropriately formatted YAML file.

            Example YAML file::

                --- !Parsing
                  stop_words:
                    - a
                    - an
                    - the
                    - in
                    - 'on'  # NOTE: 'on' without quotes is converted to True

                  translations:
                    catch: get
                    pick: get
                    take: get
                    scoop: get
                    fill: get
                    collect: get
        Args:
            parsing_data_fp (str): file path of a YAML encoded parsing data

        Returns:
            An InputParser
        """
        def constructor(loader, node):
            """defines a constructor for a PyYAML loader"""
            data = loader.construct_mapping(node, deep=True)
            stop_words = data['stop_words']
            synonyms = data['synonyms']
            return cls(stop_words=stop_words, synonyms=synonyms)

        yaml.add_constructor('!Parsing', constructor, Loader=yaml.SafeLoader)
        with open(parsing_data_fp, 'r') as f:
            input_parser = yaml.safe_load(stream=f)
        return input_parser


class _Scene:
    """
    Contains a list of possible actions.

    Note:
        A scene must always contain the '_arrive' action

    Args:
        key (str): name of the Scene
        actions_list (list of _Action): list containing all possible actions in a scene

    Attributes:
        key (str): name of the scene
        actions (dict of _Action): dict containing all possible actions in a scene by their key
    """
    def __init__(self, key, actions_list):
        self.key = key
        self.check_duplicate_action_keys(actions_list)
        self.actions = {action.key: action for action in actions_list}

    def check_duplicate_action_keys(self, actions_list):
        if len(set(action.key for action in actions_list)) != len(actions_list):
            raise ValueError('Duplicate action key (after parsing) found in Scene: "{s}"'.format(s=self.key))

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """
        Constructor for a PyYAML loader that generates Scenes from YAF elements tagged with '!Scene'

            Example YAML element::

                - !Scene
                  id: a_unique_scene_id
                  actions:
                    - !Action
                      key: _arrive  # The mandatory '_arrive' action
                      outcomes:
                        [A LIST OF OUTCOMES FOR THE '_arrive' ACTION]
                    [A LIST OF FURTHER ACTIONS]
        """
        data = loader.construct_mapping(node, deep=True)
        return cls(key=data['key'], actions_list=data['actions'])


class _Action:
    """
    Actions are matched against a player input to determine what happens.

    Each action contains a list of possible outcomes. Each action's key should be unique
    within a scene.

    Args:
        key (frozenset): an immutable set of words that uniquely identifies the actions per scene
        outcomes (list of _Outcome): list containing all possible outcomes for the actions

    Attributes:
        key (frozenset): a unique set of keywords that identify the actions
        outcomes (list of _Outcome): list containing all possible outcomes for the actions
    """

    def __init__(self, key, outcomes):
        self.key = key
        self.outcomes = outcomes

    @classmethod
    def make_pyyaml_constructor(cls, input_parser):
        """
        Creates a PyYAML constructor for actions with a specific input_parser.

        Args:
            input_parser (InputParser): an InputParser that will be used to process the actions keys

        Returns:
            A pyyaml_constructor for actions
        """
        def pyyaml_constructor(loader, node):
            """
            Constructor for a PyYAML loader that generates actions from a YAF elements tagged with '!Action'

                Example YAML element::

                    - !Action
                      key: beach
                      outcomes:
                        [A LIST OF OUTCOMES]
            """
            data = loader.construct_mapping(node, deep=True)
            key = input_parser.make_action_key(data['key'])
            return cls(key=key, outcomes=data['outcomes'])
        return pyyaml_constructor


class _Outcome:
    """
    Models one of one or many possible results of a particular action.

    Upon an outcome being executed, contingent on all of the outcome's requirements being met,
    the player's state will be altered by any mutators associated with the outcome. Every outcome
    must have some descriptive "text".

    Examples:
        1. Player WITHOUT 'knife' in inventory attempts cut a rope in the scene by inputting "cut rope".
        The outcome may be that the rope remains intact, since a "has knife" requirement was not met.
        An msg saying so could be displayed if the requirement was instead "not has knife".
        2. Player WITH 'knife' in inventory attempts cut a rope in the scene by inputting "cut rope".
        The outcome may be that the rope is cut and placed in their inventory, since a "has knife"
        requirement was met. A msg, from outcome.text, saying so will be displayed.

    Args:
        text (list of str): A list of paragraphs describing the outcome
        requirements (list of _Requirement): A list of the requirements necessary to trigger the outcome
        mutators (list of _Mutator): A list of the mutators applied when the outcome is triggered

    Attributes:
        text (list of str): A list of paragraphs describing the outcome
        requirements (list of _Requirement): A list of the requirements necessary to trigger the outcome
        mutators (list of _Mutator): A list of the mutators applied when the outcome is triggered
    """

    def __init__(self, text, requirements=None, mutators=None):
        self.text = text
        self.requirements = requirements if requirements else []
        self.mutators = mutators if mutators else []

    def check_requirements(self, player):
        """
        Determines if all requirements associated with an outcome are met

        Args:
            player (Player): The player of the game

        Returns:
            True if no requirements or if all requirements met else False
        """
        return all(requirement.check_func(player) for requirement in self.requirements)

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """
        Constructor for a PyYAML loader that generates outcomes from a YAF elements tagged with '!Outcome'

            Example YAML element::

                - !Outcome
                  requirements:
                    [AN OPTIONAL LIST OF REQUIREMENTS]
                  mutators:
                    [AN OPTIONAL LIST OF MUTATORS]
                  text:
                    - >
                      Some descriptive text
                    - >
                      Another paragraph of text

        Returns:
            An outcome
        """
        data = loader.construct_mapping(node, deep=True)
        return cls(text=data.get('text'), requirements=data.get('requirements'), mutators=data.get('mutators'),)


class _Requirement:
    """
    Models a singular check on the state of the player.

    Args:
        check_func (function): A function with a single arg 'player' that returns a boolean value given some check

    Attributes:
        check_func (function): A function with a single arg 'player' that returns a boolean value given some check
    """

    def __init__(self, check_func):
        self.check_func = check_func

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """
        Constructor for a PyYAML loader that generates requirements from YAF elements tagged with '!requirement'

            Example YAML element::

                - !Requirement
                  type: has_item
                  target: knife

        Returns:
            An outcome
        """
        data = loader.construct_mapping(node, deep=True)
        return cls(check_func=_Requirement.make_check_fnc(type_=data.get('type'), target=data.get('target')))

    @staticmethod
    def make_check_fnc(type_, target):
        """
        Choose from a selection of possible check functions

        Args:
            type_ (str): the type of check, e.g. to check if an item is in the player's inventory use 'has_item'
            target (str): the name of the key being searched for

        Returns:
            a function which applies the selected check
        """
        if type_ == 'has_item':
            def check_func(player):
                return target in player.inventory
        elif type_ == 'not_has_item':
            def check_func(player):
                return target not in player.inventory
        elif type_ == 'has_state':
            def check_func(player):
                return target in player.states
        elif type_ == 'not_has_state':
            def check_func(player):
                return target not in player.states
        elif type_ == 'has_visited':
            def check_func(player):
                return target in player.visited_scene_names
        elif type_ == 'not_has_visited':
            def check_func(player):
                return target not in player.visited_scene_names
        else:
            raise ValueError
        return check_func


class _Mutator:
    """
    Changes some state on the player when applied
    Args:
        mutator_func: a function that takes a game object and makes some update to the player's state
    """

    def __init__(self, mutator_func):
        self.mutator_func = mutator_func

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """
        Constructor for a PyYAML loader that generates a mutator from YAF elements tagged with '!Mutator'

            Example YAML element::

                - !Requirement
                  type: has_item
                  target: knife
        """
        data = loader.construct_mapping(node, deep=True)
        return cls(mutator_func=_Mutator.make_mutator_func(type_=data.get('type'), target=data.get('target')))

    @staticmethod
    def make_mutator_func(type_, target=None):
        """
        Choose from a selection of possible mutators

        Args:
            type_ (str): the type of mutator, e.g. to move a player to a new scene 'player_move_to'
            target (str): the name of the key to set, e.g. 'beach'

        Returns:
            a function which applies the selected state mutation
        """
        if type_ == 'player_move_to':
            def mutator_func(game):
                game.player.current_scene = game.scenes[target]
        elif type_ == 'player_arrive':
            def mutator_func(game):
                game.player.visited_scene_names.add(game.scenes[target].key)
        elif type_ == 'add_item':
            def mutator_func(game):
                game.player.inventory.add(target)
        elif type_ == 'remove_item':
            def mutator_func(game):
                game.player.inventory.remove(target)
        elif type_ == 'add_state':
            def mutator_func(game):
                game.player.states.add(target)
        elif type_ == 'remove_state':
            def mutator_func(game):
                game.player.states.remove(target)
        elif type_ == 'game_end':
            def mutator_func(game):
                game._in_progress = False
        else:
            raise ValueError('"{t}" is not a valid mutator type'.format(t=type_))
        return mutator_func


class Shell:
    # TODO: DOCUMENTATION

    def __init__(self, width, indentation='    '):
        self.usable_width = width - 2 * len(indentation)
        self.indentation = indentation

    def print(self, paragraphs, alignment):
        # TODO: DOCUMENTATION
        for paragraph in paragraphs:
            if alignment == 'left':
                print(indent(text=fill(text=paragraph, width=self.usable_width), prefix=self.indentation))
            elif alignment == 'centre':
                lines = wrap(text=paragraph, width=self.usable_width)
                print(*[self.indentation + str.center(l, self.usable_width) for l in lines], sep='\n')
            print()  # pad bottom of paragraphs

    def get_player_input(self, message=None):
        # TODO: DOCUMENTATION
        # TODO add some checks in here
        player_input = None
        if message:
            message = message + ' > '
        else:
            message = '> '
        while not player_input:
            player_input = input(
                indent(
                    text=fill(text=message, width=self.usable_width, drop_whitespace=False),
                    prefix=self.indentation
                )
            ).lower()
            player_input = ''.join(cha for cha in player_input if cha.isalnum() or cha == ' ')
            print()  # pad player input
        return player_input

    def pause(self):
        # TODO: DOCUMENTATION
        if OS_NAME == 'nt':
            self.print(paragraphs=["Press any key to continue..."], alignment='left')
            _ = msvcrt.getch()
        else:
            command = 'read -s -n 1 -p "{i}Press any key to continue..."'.format(i=self.indentation)
            os.system(command=command)

    @staticmethod
    def clear():
        # TODO: DOCUMENTATION
        os.system(command='cls' if OS_NAME == 'nt' else 'clear')
        print()  # pad top of screen


class Player:
    # TODO: DOCUMENTATION

    def __init__(self, initial_scene, initial_inventory, states, visited_scene_names):
        self.current_scene = initial_scene
        self.inventory = initial_inventory
        self.states = states
        self.visited_scene_names = visited_scene_names

    def save(self, fp):
        # TODO: DOCUMENTATION
        with open(file=fp, mode='wb') as f:
            dump(obj=self, file=f)

    def load(self, fp):
        # TODO
        pass
