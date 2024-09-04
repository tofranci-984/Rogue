import curses
import json
# import random
import pickle
import logging
import datetime
import random
import pygame
from typing import Tuple

pygame.init()
pygame.mixer.init()

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logging.basicConfig(filename='log.txt', filemode='w', format='%(asctime)s %(message)s',
                    level=logging.DEBUG)  # filemode= w will overwrite file each time


class Weapon:
    def __init__(self, name, damage, attack_range):
        self.name = name
        self.damage = damage
        self.attack_range = attack_range
        # logger.debug(f"Creating weapon '{name}' with damage of {damage}")


class Enemy:
    def __init__(self, name, hp, damage, sense_range, level, xp):
        self.name = name
        self.hp = hp
        self.damage = damage
        self.sense_range = sense_range
        self.level = level
        self.xp = xp
        # logger.debug(f"Creating enemy {name} with {hp} HP and damage of {damage}")


class Player:
    def __init__(self, name, hp, weapons, gold=0):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.weapon = weapons[0]  # default weapon
        self.gold = gold
        self.mana = 5
        self.max_mana = self.mana
        self.strength = 10
        self.dexterity = 10
        self.max_strength = self.strength
        self.max_dexterity = self.dexterity
        self.xp = 0
        self.level = 1

        self.items = []
        self.items.append(self.weapon)
        logger.debug(f"Creating Player {name} with {hp} HP and a {self.weapon.name}")


class Game:
    def __init__(self):
        """
        Initialize the game.
        """
        logger.debug("\nCreate Game")

        # Initialize curses screen
        self.screen = curses.initscr()
        if curses.has_colors():
            curses.start_color()
        curses.curs_set(0)
        self.screen.keypad(True)

        # Initialize game variables
        self.terminal_height, self.terminal_width = self.screen.getmaxyx()
        if self.terminal_width < 80 or self.terminal_height < 24:
            raise ValueError(
                f"Terminal size must be at least 80x24.  Is currently {self.terminal_width}, {self.terminal_height}")

        # Create separate windows for each section
        self.game_window = curses.newwin(self.terminal_height - 3, self.terminal_width - 20, 0, 0)
        self.message_window = curses.newwin(3, self.terminal_width - 21, self.terminal_height - 6, 0)
        self.legend_window = curses.newwin(self.terminal_height - 3, 20, 0, self.terminal_width - 20)
        self.status_window = curses.newwin(3, 20, self.terminal_height - 6, self.terminal_width - 20)

        self.player = None
        self.enemies = []
        self.weapons = []
        self.level = 1  # initial level
        self.event_log = []
        self.xp = 0

        # initialize message window
        # self.message_window = curses.newwin(3, self.terminal_width, self.terminal_height - 3, 0)
        # self.message_window.scrollok(True)
        self.message_log = []

        # self.game_window = curses.newwin(self.terminal_height - 3, self.terminal_width, 0, 0)
        # self.message_window = curses.newwin(3, self.terminal_width, self.terminal_height - 3, 0)
        self.message_window.scrollok(True)

        # Load weapon and enemy data
        self.load_weapons()
        self.load_enemies()

        # Initialize level variables
        self.level_width = 0
        self.level_height = 0
        self.grid = []
        self.entry_point = (0, 0)
        self.exit_point = (0, 0)
        self.show_debug_info = True

        # Load level data
        level_data = self.load_level()
        if level_data:
            self.player_pos = list(level_data['entry_point'])  # this may be outside the viewport
            self.grid[int(self.player_pos[1])][int(self.player_pos[0])] = '@'
        else:
            logger.error("Failed to load level data")
            self.add_message("Error: Failed to load level data")

        # Initialize color pairs
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Walls
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Start and Exit
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)  # Monsters
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Player
        curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Player and Gold

        # Load sound effects
        self.volume = 0.5  # Default volume (50%)
        self.gold_sound = pygame.mixer.Sound("sounds/coin.wav")
        self.enemy_sound = pygame.mixer.Sound("sounds/heal.wav")
        # self.soundON = True
        self.soundON = False

        # Initialize viewport
        self.legend_width = 20  # Adjust this value based on your legend's content
        self.viewport_width = self.terminal_width - self.legend_width - 1  # -1 is for border between legend
        self.viewport_height = self.terminal_height - 1  # -1 is for the status bar at the bottom
        self.calculate_viewport()

    def update_message_window(self):
        """
        Update the message window with the latest messages.
        """
        self.message_window.erase()
        for i, message in enumerate(self.message_log[-3:]):
            max_message_length = self.message_window.getmaxyx()[1] - 2  # subtract 2 for padding
            if len(message) > max_message_length:
                message = message[:max_message_length] + '...'  # truncate message and add ellipsis
            self.message_window.addstr(i, 0, message)

        self.message_window.refresh()

    def add_message(self, message):
        """
        Add a message to the message log.
        """
        self.message_log.append(message)
        self.update_message_window()

    def calculate_viewport(self):
        new_viewport_x = self.player_pos[0] - self.viewport_width // 2
        new_viewport_y = self.player_pos[1] - self.viewport_height // 2
        self.viewport_x = max(0, min(new_viewport_x, self.level_width - self.viewport_width))
        self.viewport_y = max(0, min(new_viewport_y, self.level_height - self.viewport_height))

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))  # Ensure volume is between 0 and 1
        # self.move_sound.set_volume(self.volume)
        self.gold_sound.set_volume(self.volume)
        self.enemy_sound.set_volume(self.volume)

    def increase_volume(self):
        self.set_volume(self.volume + 0.1)
        self.add_message(f"Volume increased to {int(self.volume * 100)}%")

    def decrease_volume(self):
        self.set_volume(self.volume - 0.1)
        self.add_message(f"Volume decreased to {int(self.volume * 100)}%")

    def move_player(self, dy, dx):
        new_y = self.player_pos[1] + dy
        new_x = self.player_pos[0] + dx

        if 0 <= new_y < self.level_height and 0 <= new_x < self.level_width:
            new_cell = self.grid[new_y][new_x]
            logger.debug(f"new_cell={new_cell}, dy={dy}, dx={dx}, new_y={new_y}, new_x={new_x}")

            # Check for adjacent monsters
            monster_adjacent = False
            for y in range(max(0, new_y - 1), min(self.level_height, new_y + 2)):
                for x in range(max(0, new_x - 1), min(self.level_width, new_x + 2)):
                    if self.grid[y][x] == 'E':
                        # player is moving near or on Enemy
                        logger.debug(f"Enemy in range!, dy={dy}, dx={dx}, new_y={new_y}, new_x={new_x}, y={y}, x={x}")
                        if (new_cell != 'E'):  # prevent being in same cell as enemy
                            self.grid[self.player_pos[1]][self.player_pos[0]] = '.'
                            self.grid[new_y][new_x] = '@'
                            self.player_pos = (new_x, new_y)
                            # self.add_message("Enemy is in range! Prepare to fight!")
                            monster_adjacent = True

                            # Start combat
                            eligible_enemies = [enemy for enemy in self.enemies if enemy.level <= self.player.level]
                            if eligible_enemies:
                                enemy = random.choice(eligible_enemies)
                            else:
                                # Handle the case where there are no enemies at or below the player's level
                                # For example, you could add a message to the player or choose an enemy at a higher level
                                logger.debug(f"No enemies at or below your level!: LVL={self.player.level}")
                                enemy = random.choice(self.enemies)
                            while self.player.hp > 0 and enemy.hp > 0:
                                self.add_message(f"You are in combat with a {enemy.name}!")
                                # action = input("Do you want to (A)ttack or (F)lee? ")
                                action = 'A'
                                if action.upper() == "A":
                                    # Player attacks
                                    attack_damage = random.randint(1, self.player.weapon.damage)
                                    enemy.hp -= attack_damage
                                    self.add_message(
                                        f"You attack {enemy.name} for {attack_damage} damage.  {enemy.name} has {enemy.hp} HP remaining.")
                                    if self.soundON: self.enemy_sound.play()

                                    if enemy.hp <= 0:
                                        self.add_message(f"\nYou defeated {enemy.name}!")
                                        self.enemies.remove(enemy)
                                        self.player.xp += enemy.xp
                                        break

                                    # Enemy attacks
                                    attack_damage = random.randint(1, enemy.damage)
                                    self.player.hp -= attack_damage
                                    self.add_message(f"{enemy.name} attacks you for {attack_damage} damage.  ")

                                    if self.player.hp <= 0:
                                        self.add_message(f"You have been defeated by the {enemy.name}!")
                                        self.game_over = True
                                        break

                                elif action.upper() == "F":
                                    # Player flees
                                    self.add_message("You attempt to flee!")
                                    direction = input(
                                        "Which direction do you want to move? (N)orth, (S)outh, (E)ast, (W)est? ")
                                    if direction.upper() == "N":
                                        new_y = self.player_pos[1] - 1
                                        new_x = self.player_pos[0]
                                    elif direction.upper() == "S":
                                        new_y = self.player_pos[1] + 1
                                        new_x = self.player_pos[0]
                                    elif direction.upper() == "E":
                                        new_y = self.player_pos[1]
                                        new_x = self.player_pos[0] + 1
                                    elif direction.upper() == "W":
                                        new_y = self.player_pos[1]
                                        new_x = self.player_pos[0] - 1
                                    else:
                                        self.add_message("Invalid direction!")
                                        continue

                                    # Check if the new position is within the grid
                                    if 0 <= new_x < len(self.grid[0]) and 0 <= new_y < len(self.grid):
                                        self.grid[self.player_pos[1]][self.player_pos[0]] = '.'
                                        self.grid[new_y][new_x] = '@'
                                        self.player_pos = (new_x, new_y)
                                        self.add_message("You successfully fled!")
                                        break
                                    else:
                                        self.add_message("You cannot move that way!")
                                        continue

                                else:
                                    self.add_message("Invalid action!")
                                    continue

                        # break
                if monster_adjacent:
                    break

            if not monster_adjacent:
                if new_cell == '.' or new_cell == '@':  # floor or player
                    # Move to empty space or current position
                    self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace with blank
                    self.grid[new_y][new_x] = '@'
                    self.player_pos = [new_x, new_y]
                    self.add_message("You moved.")
                elif new_cell == '#':  # wall
                    self.add_message("You bumped into a wall.")
                elif new_cell == 'G':
                    self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace gold with blank
                    self.grid[new_y][new_x] = '!'
                    self.player_pos = [new_x, new_y]
                    self.add_message ("You have found treasure!")
                    self.gold_sound.play()
                    # insert treasure logic here
                    self.player.gold += random.randint(1, 100)
                elif new_cell == '^':  # trap
                    self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace trap with blank
                    self.grid[new_y][new_x] = '!'
                    self.player_pos = [new_x, new_y]
                    hp = random.randint(1, int(self.player.hp / 3))
                    self.player.hp -= hp
                    self.add_message (f"You have triggered a trap! You suffered {hp} damage!")
                    self.enemy_sound.play()
                    if self.player.hp <= 0:  # should never happen as we choose hp from 1 to hp / 3
                        self.add_message ("You have been defeated by the trap!")
                        self.game_over = True
                elif new_cell == 'X':
                    self.add_message("You found the exit!")
                    self.game_over = True
                    # Add level completion logic here
                else:
                    logger.debug(f"Unknown object encountered {new_cell} at new_y:{new_y}, new_x:{new_x}")
                    self.add_message(f"You encountered an unknown object: {new_cell}")

            if self.player_pos != (new_x, new_y):  # Only update if the player actually moved
                self.player_pos = [new_x, new_y]
                self.calculate_viewport()  # Update viewport after moving player

    def load_weapons(self):
        logger.debug(f"Loading weapons from 'game/weapons.json'")

        with open('game/weapons.json') as f:
            weapons_data = json.load(f)
        for weapon in weapons_data:
            self.weapons.append(Weapon(**weapon))
        logger.debug(f"Loaded {len(self.weapons)} weapons")

    def load_enemies(self):
        logger.debug(f"Loading enemies from 'game/enemies.json'")
        with open('game/enemies.json') as f:
            enemies_data = json.load(f)
        for enemy in enemies_data:
            self.enemies.append(Enemy(**enemy))
        logger.debug(f"Loaded {len(self.enemies)} enemies")

    def generate_level(self):
        # Logic for generating a random level
        pass

    def load_level(self):
        filename = f"game/level_{self.level}"
        logger.debug(f"Loading level {self.level} from {filename}")
        try:
            with open(filename, 'r') as f:
                level_data = json.load(f)
            self.level_width = level_data['width']
            self.level_height = level_data['height']
            self.grid = [list(row) for row in level_data['grid']]
            self.entry_point = level_data['entry_point']
            self.exit_point = level_data['exit_point']
            self.add_message(f"Level {self.level} loaded successfully")
            logger.debug(
                f"Level data: width={self.level_width}, height={self.level_height}, grid size={len(self.grid)}x{len(self.grid[0]) if self.grid else 0}")
            return level_data
        except FileNotFoundError:
            logger.error(f"File {filename} not found")
            self.add_message(f"Error: Level {self.level} not found")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {filename}")
            self.add_message(f"Error: Invalid level data for level {self.level}")
        except Exception as e:
            logger.error(f"Unexpected error loading level: {str(e)}")
            self.add_message(f"Error: Failed to load level {self.level}")
        return None

    def update_game_state(self):
        # Move monster towards player if within 5 cells
        player_x, player_y = self.player_pos
        for enemy in self.enemies:
            if enemy.symbol == 'M':
                monster_x, monster_y = enemy.pos
                if abs(player_x - monster_x) <= 5 and abs(player_y - monster_y) <= 5:
                    dx = player_x - monster_x
                    dy = player_y - monster_y
                    if abs(dx) > abs(dy):
                        if dx > 0:
                            enemy.pos = (monster_x + 1, monster_y)
                        else:
                            enemy.pos = (monster_x - 1, monster_y)
                    else:
                        if dy > 0:
                            enemy.pos = (monster_x, monster_y + 1)
                        else:
                            enemy.pos = (monster_x, monster_y - 1)


    def save_game(self):
        logger.debug("save_game()")
        with open('savegame.pkl', 'wb') as f:
            pickle.dump((self.player, self.enemies, self.level), f)

    def load_game(self):
        logger.debug("load_game()")
        with open('savegame.pkl', 'rb') as f:
            self.player, self.enemies, self.level = pickle.load(f)


    def handle_input(self):
        key = self.screen.getch()
        if key == ord('q'):
            return False
        elif key == ord('s'):
            self.save_game()
        elif key == ord('l'):
            self.load_game()
        elif key == curses.KEY_UP:
            self.move_player(-1, 0)
        elif key == curses.KEY_DOWN:
            self.move_player(1, 0)
        elif key == curses.KEY_LEFT:
            self.move_player(0, -1)
        elif key == curses.KEY_RIGHT:
            self.move_player(0, 1)
        elif key == ord('+'):
            self.increase_volume()
        elif key == ord('-'):
            self.decrease_volume()
        elif key == ord('S'):  # Shift-D (capital S in curses)
            self.show_debug_info = not self.show_debug_info
            self.add_message("Debug info toggled")

        return True

    def update(self):
        # Calculate available space for legend
        available_width = self.terminal_width - self.legend_width
        legend_start_x = min(self.level_width, available_width - self.legend_width)

        # Clear all windows
        self.game_window.erase()
        self.message_window.erase()
        self.legend_window.erase()
        self.status_window.erase()

        # Print the visible portion of the level
        for y in range(self.viewport_height):
            for x in range(self.viewport_width):
                level_y = y + self.viewport_y
                level_x = x + self.viewport_x
                if 0 <= level_y < self.level_height and 0 <= level_x < self.level_width:
                    cell = self.grid[level_y][level_x]
                    try:
                        if cell == '#':
                            self.game_window.addch(y, x, cell, curses.color_pair(1))
                        elif cell in ['S', 'X']:
                            self.game_window.addch(y, x, cell, curses.color_pair(2))
                        elif cell == 'E':
                            self.game_window.addch(y, x, cell, curses.color_pair(3))
                        elif cell in ['@']:
                            self.game_window.addch(y, x, cell, curses.color_pair(5))
                        elif cell in ['$']:
                            self.game_window.addch(y, x, '$', curses.color_pair(4))
                        elif cell in ['T']:
                            self.game_window.addch(y, x, 'T', curses.color_pair(4))
                        else:
                            self.game_window.addch(y, x, cell)
                    except curses.error:
                        pass

        # Draw border between level and legend
        for y in range(self.viewport_height):
            if y < self.game_window.getmaxyx()[0] and self.viewport_width < self.game_window.getmaxyx()[1]:
                self.game_window.addch(y, self.viewport_width -1, '|')

        # Print the legend
        if self.show_debug_info:
            debug_info = f"Player: ({self.player_pos[0]}, {self.player_pos[1]})"
            debug_info += f" Viewport: ({self.viewport_x}, {self.viewport_y})"
            self.legend_window.addstr(0, 0, debug_info[:self.legend_width])

        self.legend_window.addstr(1, 0, "Legend:")
        legend_entries = [
            ("#", "Wall", 1),
            ("S/X", "Start/Exit", 2),
            ("E", "Monster", 3),
            ("@", "Player", 5),
            (f"{self.player.gold}", "Gold", 4)
        ]
        for i, (symbol, description, color) in enumerate(legend_entries):
            if 2 + i < self.viewport_height:
                self.legend_window.addstr(2 + i, 0, symbol, curses.color_pair(color))
                self.legend_window.addstr(2 + i, 2, f"- {description}"[:self.legend_width - 2])

        # Display player stats
        stats = [
            ("HP", self.player.hp, self.player.max_hp),
            ("Mana", self.player.mana, self.player.max_mana),
            ("Strength", self.player.strength, self.player.max_strength),
            ("Dexterity", self.player.dexterity, self.player.max_dexterity)
        ]
        for i, (label, value, max_value) in enumerate(stats):
            if 9 + i < self.legend_window.getmaxyx()[0]:
                color = 2 if value >= max_value * 0.25 else 3
                stat_str = f"{value}/{max_value} - {label}"
                self.legend_window.addstr(9 + i, 0, stat_str, curses.color_pair(color))
        self.legend_window.refresh()

        # Display the message
        for i, message in enumerate(self.message_log[-3:]):
            self.message_window.addstr(i, 0, message)

        # Refresh all windows
        self.game_window.refresh()
        self.message_window.refresh()
        self.legend_window.refresh()
        self.status_window.refresh()


    def render(self):
        # Render game state
        self.screen.refresh()

    def run(self):
        # create player

        self.player = Player("New Player", 25, self.weapons)

        self.update()
        self.render()
        while True:
            if not self.handle_input():
                break
            self.update()
            self.render()
        curses.endwin()


if __name__ == "__main__":
    logger.debug("Start main")

    # with open('game/enemies.json', 'r') as f:
    #     enemies = json.load(f)
    #
    # for enemy in enemies:
    #     enemy['exp'] = random.randint(enemy['level'], enemy['level'] * 10)
    #
    # with open('game/enemies.json', 'w') as f:
    #     json.dump(enemies, f, indent=4)

    game = Game()
    game.run()
