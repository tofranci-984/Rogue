import curses
import json
import pickle
import logging
import random
import pygame
import os
from rich import print
from rich.console import Console
from rich.text import Text

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

class Enemy:
    def __init__(self, name, hp, damage, sense_range, level, xp):
        self.name = name
        self.hp = hp
        self.start_hp = None
        self.start_hp = hp
        self.damage = damage
        self.sense_range = sense_range
        self.level = level
        self.xp = xp

class Potion:
    def __init__(self, type):
        if type == "health":
            self.name = "Health Potion"
            self.description = "Restores 10 health"
            self.health_restored = 10
        elif type == "mana":
            self.name = "Mana Potion"
            self.description = "Restores 10 mana"
            self.mana_restored = 10
        elif type == "strength":
            self.name = "Strength Potion"
            self.description = "Increases strength by 10%"
            self.strength_increase = 10

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
        self.max_xp = 20  # 20 xp needed for next level
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

        # Initialize viewport
        self.legend_width = 35  # Adjust this value based on your legend's content
        self.legend_height = 20  # Adjust this value based on your legend's content
        self.viewport_width = 40
        self.viewport_height = 20
        self.viewport_x = 0
        self.viewport_y = 0

        self.player = None
        self.enemies = []
        self.weapons = []
        self.level_filename = "1.lvl"  # initial level
        self.level = 1
        self.event_log = []
        self.xp = 0
        self.message_log = []
        self.level_height = 40
        self.level_width = 20
        self.game_over = False

        self.grid = []
        self.entry_point = (0, 0)
        self.exit_point = (0, 0)
        self.show_debug_info = True

        message_window_height = 3
        self.message_window = curses.newwin(4, 40, 20, 0)
        self.message_window.scrollok(True)
        self.message_window.bkgd(" ", curses.color_pair(2))

        self.messages = []

        # Load weapon and enemy data
        self.load_weapons()
        self.load_enemies()

        # Load level data
        level_data = self.load_level()
        if level_data:
            self.player_pos = list(level_data['entry_point'])  # this may be outside the viewport
            self.grid[int(self.player_pos[1])][int(self.player_pos[0])] = '@'
        else:
            logger.error("Failed to load level data")
            self.add_message("Error: Failed to load level data")

        # Create separate windows for each section
        if self.level_width + self.legend_width < self.terminal_width:
            game_window_width = self.level_width
        else:
            game_window_width = 40  # max game window width
        if self.level_height + self.legend_height < self.terminal_height:
            game_window_height = self.level_height
        else:
            game_window_height = 20  # max game window height

        self.game_window = curses.newwin(game_window_height, game_window_width, 0, 0)
        self.game_window.bkgd(" ", curses.color_pair(3))

        self.legend_window = curses.newwin(self.terminal_height, self.legend_width, 0, self.viewport_width + 1)
        self.legend_window.bkgd(" ", curses.color_pair(1))
        # self.legend_window = curses.newwin(game_window_height, self.legend_width, 0, self.viewport_width + 1)

        if self.viewport_width > self.level_width:
            self.viewport_width = self.level_width
        if self.viewport_height > self.level_height:
            self.viewport_height = self.level_height

        # Calculate viewport
        self.calculate_viewport()

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
        self.add_message("Game initialized")

    import curses

    def parse_message(self, message):
        result = ""
        attrs = 0
        for part in message.split("["):
            if part.startswith("b]"):
                attrs |= curses.A_BOLD
                result += part[2:]
            elif part.startswith("/b]"):
                attrs &= ~curses.A_BOLD
                result += part[3:]
            elif part.startswith("red]"):
                attrs |= curses.COLOR_RED
                result += part[4:]
            elif part.startswith("/red]"):
                attrs &= ~curses.COLOR_RED
                result += part[5:]
            elif part.startswith("u]"):
                attrs |= curses.A_UNDERLINE
                result += part[2:]
            elif part.startswith("/u]"):
                attrs &= ~curses.A_UNDERLINE
                result += part[3:]
            else:
                result += part
                # result += "[" + part
        return result, attrs

    def update_message_window(self, message_window_height=4):
        max_width = self.message_window.getmaxyx()[1]
        lines = []
        message_window_height -= 1  # Subtract 1 for the title line
        for message in self.message_log[-message_window_height:]:
            formatted_message, attrs = self.parse_message(message)
            words = formatted_message.split()
            current_line = ""
            for word in words:
                if len(current_line + " " + word) > max_width:
                    lines.append((current_line.strip(), attrs))
                    current_line = word
                else:
                    current_line += " " + word
            if current_line:
                lines.append((current_line.strip(), attrs))

        self.message_window.erase()
        self.message_window.clear()
        for i, (line, attrs) in enumerate(lines):
            self.message_window.addstr(i, 0, line, attrs)
        self.message_window.refresh()

    def add_message(self, message, message_window_height=4):
        """
        Add a message to the message log.
        """
        self.message_log.append(message)
        logger.debug(f"{message}")
        self.message_window.erase()
        self.update_message_window(message_window_height)

    def calculate_viewport(self):
        new_viewport_x = self.player_pos[0] - self.viewport_width // 2
        new_viewport_y = (self.player_pos[1] + 1) - self.viewport_height // 2  # + 1 to account for the status bar
        self.viewport_x = max(0, min(new_viewport_x, self.level_width - self.viewport_width))
        self.viewport_y = max(0, min(new_viewport_y, self.level_height - self.viewport_height))
        # new_viewport_x = self.player_pos[0] - self.viewport_width // 2
        # new_viewport_y = self.player_pos[1] - self.viewport_height // 2
        # self.viewport_x = max(0, min(new_viewport_x, self.level_width - self.viewport_width))
        # self.viewport_y = max(0, min(new_viewport_y, self.level_height - self.viewport_height))

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
        move_player = True
        monster_adjacent = False

        if 0 <= new_y < self.level_height and 0 <= new_x < self.level_width:
            new_cell = self.grid[new_y][new_x]
            logger.debug(f"new_cell={new_cell}, dy={dy}, dx={dx}, new_y={new_y}, new_x={new_x}")

            # Check for adjacent monsters
            monster_adjacent = False
            for y in range(max(0, new_y - 1), min(self.level_height, new_y + 2)):
                for x in range(max(0, new_x - 1), min(self.level_width, new_x + 2)):
                    if self.grid[y][x] == 'E':  # check for adjacent monsters
                        # player is moving near or on Enemy
                        logger.debug(f"Enemy in range!, dy={dy}, dx={dx}, new_y={new_y}, new_x={new_x}, y={y}, x={x}")
                        if new_cell != 'E':  # prevent being in same cell as enemy
                            self.grid[self.player_pos[1]][self.player_pos[0]] = '.'
                            self.grid[new_y][new_x] = '@'
                            self.player_pos = (new_x, new_y)
                            self.game_window.refresh()
                            monster_adjacent = True

                            # Start combat
                            eligible_enemies = [enemy for enemy in self.enemies if enemy.level <= self.player.level]
                            if eligible_enemies:
                                enemy = random.choice(eligible_enemies)
                            else:
                                # Handle the case where there are no enemies at or below the player's level
                                # For example, you could add a message to the player or choose an enemy at a higher level
                                logger.debug(f"No enemies at or below your level!: LVL={self.player.level}")
                                enemy = random.choice(self.enemies)  # Choose a random enemy

                            self.message_window.erase()
                            self.message_window.refresh()

                            # Expand message log for combat
                            self.message_window.resize(self.viewport_height, self.viewport_width)
                            self.message_window.mvwin(0, 0)
                            self.message_window.refresh()

                            while self.player.hp > 0 and enemy.hp > 0:
                                self.add_message(f"You are in range of a {enemy.name}!", 20)
                                self.add_message("Do you want to (A)ttack or (F)lee? ", 20)
                                key = -1
                                while key == -1:
                                    key = self.screen.getch()

                                self.update()

                                if key == ord('a'):
                                    # Player attacks
                                    attack_damage = random.randint(1, self.player.weapon.damage)
                                    enemy.hp -= attack_damage
                                    self.add_message(
                                        f"You attack {enemy.name} for [red]{attack_damage}[/red] damage.", 20)
                                    self.add_message(f"{enemy.name} HP ({enemy.hp}/{enemy.start_hp})", 20)
                                    if self.soundON:
                                        self.enemy_sound.play()

                                    if enemy.hp <= 0:
                                        self.add_message(f"You defeated the {enemy.name}!", 20)
                                        self.enemies.remove(enemy)
                                        self.grid[y][x] = '.'  # clear the enemy cell
                                        self.game_window.refresh()
                                        self.add_message(f"You gained {enemy.xp} XP!", 20)
                                        self.player.xp += enemy.xp
                                        # Restore message log size
                                        self.message_window.resize(4, 40)
                                        self.message_window.mvwin(20, 0)
                                        self.message_window.refresh()

                                        break

                                    # Enemy attacks
                                    attack_damage = random.randint(1, enemy.damage)
                                    self.player.hp -= attack_damage
                                    self.add_message(f"{enemy.name} attacks you for [red]{attack_damage}[/red] damage.", 20)

                                    # self.update()  # Update the game window, legend window, and message window
                                    if self.soundON:
                                        self.enemy_sound.play()

                                    if self.player.hp <= 0:
                                        self.add_message(f"You have been defeated by the {enemy.name}!", 20)
                                        self.game_over = True
                                        break
                                elif key == ord('f'):
                                    # Player flees
                                    self.add_message("You attempt to flee!", 20)
                                    self.add_message(
                                        "Which direction do you want to move? (N)orth, (S)outh, (E)ast, (W)est? ", 20)
                                    self.screen.refresh()
                                    key = self.screen.getch()
                                    if key == ord("n"):
                                        new_y = self.player_pos[1] - 1
                                        new_x = self.player_pos[0]
                                    elif key == ord("s"):
                                        new_y = self.player_pos[1] + 1
                                        new_x = self.player_pos[0]
                                    elif key == ord("e"):
                                        new_y = self.player_pos[1]
                                        new_x = self.player_pos[0] + 1
                                    elif key == ord("w"):
                                        new_y = self.player_pos[1]
                                        new_x = self.player_pos[0] - 1
                                    else:
                                        self.add_message("Invalid direction!", 20)
                                        self.screen.refresh()
                                        continue

                                        # Check if the new position is within the grid
                                    if 0 <= new_x < len(self.grid[0]) and 0 <= new_y < len(self.grid):
                                        self.grid[self.player_pos[1]][self.player_pos[0]] = '.'
                                        self.grid[new_y][new_x] = '@'
                                        self.player_pos = (new_x, new_y)
                                        self.add_message("You successfully fled!", 20)
                                        break
                                    else:
                                        self.add_message("You cannot move that way!", 20)
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
                self.game_window.refresh()
            elif new_cell == '#':  # wall
                self.add_message("You bumped into a wall.")
                move_player = False
            elif new_cell == '$' or new_cell == 'G':  # gold
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace gold with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = [new_x, new_y]
                if self.soundON:
                    self.gold_sound.play()
                new_gold = random.randint(1, 100)
                self.add_message(f"You have found {new_gold} gold!")
                self.player.gold += new_gold
            elif new_cell == 'T':  # gold
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace treasure with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = [new_x, new_y]
                if self.soundON:
                    self.gold_sound.play()
                # what kind of treasure?
                new_gold = random.randint(self.player.level * 10, 100 + self.player.level * 10)
                self.add_message(f"You have found {new_gold} gold!")
                self.player.gold += new_gold
                if random.randint(1, 1) == 1:  # 1/10 chance of getting a weapon
                    weapon_name = random.choice([weapon.name for weapon in self.weapons])
                    weapon_damage = random.randint(1, 5)
                    self.player.items.append(Weapon(weapon_name, weapon_damage, 1))  # assuming attack_range is 1
                    self.add_message(f"You found a {self.player.items[-1].name}!")
            elif new_cell == '^':  # trap
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace trap with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = [new_x, new_y]
                if self.player.hp > 0:
                    hp = random.randint(1, int(self.player.hp / 3))
                else:
                    hp = 0
                self.player.hp -= hp
                self.add_message(f"You have triggered a trap! You suffered {hp} damage!")
                if self.soundON:
                    self.enemy_sound.play()
                if self.player.hp <= 0:  # should never happen as we choose hp from 1 to hp / 3
                    self.add_message("You have been defeated by the trap!")
                    self.game_over = True
            elif new_cell == '>':  # stairs down
                self.add_message("You found stairs going down")
                self.level += 1
                self.level_filename = f"{self.level}.lvl"
                self.load_level()
                self.player_pos = self.entry_point
                move_player = False
            elif new_cell == '<':  # stairs up
                self.add_message("You found stairs going up")
                self.level -= 1
                self.level_filename = f"{self.level}.lvl"
                self.load_level()
                self.player_pos = self.entry_point
                move_player = False
            elif new_cell == 'H':  # health potion
                self.add_message("You found a health potion")
                self.player.items.append(Potion("health"))
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace potion with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = [new_x, new_y]
                if self.soundON:
                    self.gold_sound.play()
            elif new_cell == 'M':  # mana potion
                self.add_message("You found a mana potion")
                self.player.items.append(Potion("mana"))
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace potion with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = [new_x, new_y]
                if self.soundON:
                    self.gold_sound.play()
            elif new_cell == 'P':  # random potion
                if random.randint(0, 1) == 0:
                    self.add_message("You found a health potion")
                    self.player.items.append(Potion("health"))
                    self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace potion with blank
                    self.grid[new_y][new_x] = '!'
                    self.player_pos = [new_x, new_y]
                    if self.soundON:
                        self.gold_sound.play()
                else:
                    self.add_message("You found a mana potion")
                    self.player.items.append(Potion("mana"))
                    self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace potion with blank
                    self.grid[new_y][new_x] = '!'
                    self.player_pos = [new_x, new_y]
                    if self.soundON:
                        self.gold_sound.play()
            elif new_cell == '+':  # door
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace door with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = [new_x, new_y]
            elif new_cell == 'X':
                self.add_message("You found the exit!")
                self.game_over = True
                # Add level completion logic here
            else:
                logger.debug(f"Unknown object encountered {new_cell} at new_y:{new_y}, new_x:{new_x}")
                self.add_message(f"You encountered an unknown object: {new_cell}")
                move_player = False

            if self.player_pos != (new_x, new_y) and move_player:  # Only update if the player actually moved
                self.player_pos = [new_x, new_y]
                self.calculate_viewport()  # Update viewport after moving player
                self.update()


    def load_weapons(self):
        logger.debug(f"Loading weapons from 'game/weapons.json'")

        with open('game/weapons.json') as f:
            weapons_data = json.load(f)
        for weapon in weapons_data:
            self.weapons.append(Weapon(**weapon))
        self.add_message(f"Loaded {len(self.weapons)} weapons")

    def load_enemies(self):
        logger.debug(f"Loading enemies from 'game/enemies.json'")
        with open('game/enemies.json') as f:
            enemies_data = json.load(f)
        for enemy in enemies_data:
            self.enemies.append(Enemy(**enemy))
        self.add_message(f"Loaded {len(self.enemies)} enemies")

    def generate_level(self):
        # Logic for generating a random level
        pass

    def load_level(self):
        filename = f"levels/{self.level_filename}"
        if not filename.endswith('.lvl'):
            filename += '.lvl'
        path, filename = os.path.split(filename)
        self.add_message(f"Loading level {self.level} from {path}")
        try:
            with open(f"{path}/{filename}", 'r') as f:
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
            self.add_message(f"Error: Level {self.level} not found")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {filename}")
            self.add_message(f"Error: Invalid level data for level {self.level}, in {filename}")
        except Exception as e:
            logger.error(f"Unexpected error loading level: {str(e)}")
            self.add_message(f"Error: Failed to load level {self.level}")
        return None


    def save_game(self):
        logger.debug("save_game()")
        with open('savegame.pkl', 'wb') as f:
            pickle.dump((self.player, self.enemies, self.level), f)

    def load_game(self):
        logger.debug("load_game()")
        with open('savegame.pkl', 'rb') as f:
            self.player, self.enemies, self.level = pickle.load(f)

    def handle_input(self):

        self.screen.nodelay(True)  # do not block and wait for input
        curses.noecho()
        key = -1
        while key == -1:
            key = self.screen.getch()

        if key == ord('q'):
            return False
        elif key == ord('s'):
            self.save_game()
        elif key == ord('l'):
            # self.load_game()
            self.add_message("Game loaded")
            # return True
        elif key == 76:  # shift L
            # show message log
            self.view_message_log()
        elif key == ord('h'):
            # drink health potion
            if self.player.hp == self.player.max_hp:
                self.add_message("You already have full health!")
                return True
            for item in self.player.items:
                if isinstance(item, Potion) and item.name == "Health Potion":
                    if item.health_restored + self.player.hp > self.player.max_hp:
                        self.player.hp = self.player.max_hp
                    else:
                        self.player.hp += item.health_restored
                    self.player.items.remove(item)
                    self.add_message("You drank a health potion!")
                    break
            else:
                self.add_message("You don't have a health potion!")
        elif key == ord('m'):
            # drink health potion
            if self.player.mana == self.player.max_mana:
                self.add_message("You already have full mana!!")
                return True
            for item in self.player.items:
                if isinstance(item, Potion) and item.name == "Mana Potion":
                    if item.mana_restored + self.player.mana > self.player.max_mana:
                        self.player.mana = self.player.max_mana
                    else:
                        self.player.mana += item.mana_restored
                    self.player.items.remove(item)
                    self.add_message("You drank a mana potion!")
                    break
            else:
                self.add_message("You don't have a mana potion!")

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
        elif key == ord('u'):
            self.legend_window.refresh()
            self.update()
        elif key == ord('1'):
            self.view_message_log()
        elif key == ord('2'):
            self.legend_window.erase()
            self.legend_window.refresh()
            # self.show_inventory()
            self.change_weapon()
        elif key == ord('S'):  # Shift-D (capital S in curses)
            self.show_debug_info = not self.show_debug_info
            self.add_message("Debug info toggled")

        self.screen.nodelay(False)  # turn off nodelay / non-blocking input
        curses.echo()
        return True

    def show_inventory(self):
        # max_y, max_x = self.screen.getmaxyx()
        self.legend_window.erase()
        self.legend_window.bkgd(" ", curses.color_pair(1))
        self.legend_window.refresh()

        self.legend_window.addstr(0, 0, "Inventory:")
        self.legend_window.refresh()
        for i, item in enumerate(self.player.items):
            if isinstance(item, Weapon):
                self.legend_window.addstr(i + 1, 0, f"{i+1} {item.name} (Damage: {item.damage})", curses.color_pair(2))
            elif isinstance(item, Potion):
                if item.name == "Health Potion":
                    self.legend_window.addstr(i + 1, 0, f"{i+1} {item.name} (Restores: {item.health_restored} HP)", curses.color_pair(4))
                elif item.name == "Mana Potion":
                    self.legend_window.addstr(i + 1, 0, f"{i+1} {item.name} (Restores: {item.mana_restored} MP)", curses.color_pair(1))
                elif item.name == "Strength Potion":
                    self.legend_window.addstr(i + 1, 0, f"{i+1} {item.name} (Increases: {item.strength_increase}%)", curses.color_pair(3))
            else:
                self.legend_window.addstr(i + 1, 0, f"{i+1} {item.name}")
            self.legend_window.refresh()
        max_y, max_x = self.legend_window.getmaxyx()
        self.legend_window.addnstr(19, 0, "Weapon #, (d)rop or (q)uit", max_x - 1)
        self.legend_window.refresh()
        curses.noecho()
        key = self.screen.getch()
        curses.echo()

    def change_weapon(self):
        # Display the inventory and allow  the player to select an weapon
        self.add_message(f"Changing to new weapon")
        self.show_inventory()
        selection = self.screen.getch()  # flush out existing char

        selection = -1
        curses.noecho()

        while selection == -1:
            selection = self.screen.getch()
        curses.echo()

        selection = selection - 49  # 48 = ord('0')
        if 0 <= selection < len(self.player.items) and isinstance(self.player.items[selection], Weapon):
            self.player.weapon = self.player.items[selection]
            self.add_message(f"Changed weapon to {self.player.weapon.name}")
        else:
            self.add_message("Invalid selection {selection}  Must be a Weapon")


    def view_message_log(self):
        self.screen.clear()
        max_y, max_x = self.screen.getmaxyx()
        messages = self.message_log[:]
        offset = 0
        while True:
            self.screen.clear()
            for i, message in enumerate(messages[offset:offset + max_y - 1]):
                self.screen.addnstr(i, 0, message, max_x - 1)
            self.screen.addnstr(max_y - 1, 0, "Press 'q' to exit, 'j' to scroll down, 'k' to scroll up", max_x - 1)
            self.screen.refresh()
            key = self.screen.getch()
            if key == ord('q'):
                self.screen.clear()
                self.screen.refresh()
                break
            elif key == ord('j'):
                if offset + max_y - 1 < len(messages):
                    offset += 1
            elif key == ord('k'):
                if offset > 0:
                    offset -= 1
            self.screen.clear()
            self.screen.refresh()

    def update(self):
        # Calculate available space for legend
        available_width = self.terminal_width - self.legend_width
        legend_start_x = min(self.level_width, available_width - self.legend_width)

        # Clear all windows
        self.game_window.erase()
        # self.game_window.bkgd("g", curses.color_pair(3))
        self.game_window.refresh()
        self.message_window.erase()
        # self.message_window.bkgd("m", curses.color_pair(2))
        self.message_window.refresh()
        self.legend_window.erase()
        # self.legend_window.bkgd("x", curses.color_pair(1))
        self.legend_window.refresh()

        # Print the visible portion of the level
        for y in range(self.viewport_height):
            for x in range(self.viewport_width):
                # self.game_window.refresh()
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
                        elif cell in ['$', 'G']:
                            self.game_window.addch(y, x, '$', curses.color_pair(4))
                        elif cell in ['T', 'H', 'P']:
                            self.game_window.addch(y, x, cell, curses.color_pair(4))
                        else:
                            self.game_window.addch(y, x, cell)
                    except curses.error:
                        pass

        self.game_window.refresh()

        # Draw column separator
        self.screen.vline(0, self.viewport_width, curses.ACS_VLINE, self.viewport_height)
        self.game_window.refresh()
        self.screen.refresh()

        # Print the legend
        if self.show_debug_info:
            debug_info = f"Player: ({self.player_pos[0]}, {self.player_pos[1]})"
            debug_info += f" Viewport: ({self.viewport_x}, {self.viewport_y})"
            self.legend_window.addstr(0, 0, debug_info[:self.legend_width])

        self.legend_window.addstr(1, 0, "Legend:")
        legend_entries = [
            ("#", "Wall", 1),
            ("X", "Start/Exit", 2),
            ("</>", "Stairs up / down", 2),
            ("E", "Enemy", 3),
            ("@", "Player", 5),
        ]
        for i, (symbol, description, color) in enumerate(legend_entries):
            if 2 + i < self.viewport_height:
                self.legend_window.addstr(2 + i, 0, symbol, curses.color_pair(color))
                self.legend_window.addstr(2 + i, 3, f"- {description}"[:self.legend_width - 2])

        self.legend_window.addstr(7, 0, f"Weapon: {self.player.weapon.name} ({self.player.weapon.damage} damage)", curses.color_pair(4))

        self.legend_window.refresh()

        # Display player stats
        stats = [
            ("HP", self.player.hp, self.player.max_hp),
            ("Mana", self.player.mana, self.player.max_mana),
            ("Strength", self.player.strength, self.player.max_strength),
            ("Dexterity", self.player.dexterity, self.player.max_dexterity),
            ("XP", self.player.xp, self.player.max_xp)
        ]
        for i, (label, value, max_value) in enumerate(stats):
            if 9 + i < self.legend_window.getmaxyx()[0]:
                color = 2 if value >= max_value * 0.25 else 3
                stat_str = f"{value}/{max_value} - {label}"
                self.legend_window.addstr(9 + i, 0, stat_str, curses.color_pair(color))

        gold = f"{self.player.gold} - Gold"
        self.legend_window.addstr(14, 0, gold, curses.color_pair(4))
        self.legend_window.refresh()

        # Display player inventory
        self.legend_window.addstr(16, 0, "Inventory:")
        for i, item in enumerate(self.player.items):
            if 16 + i < self.legend_window.getmaxyx()[0]:
                if isinstance(item, Weapon):
                    self.legend_window.addstr(17 + i, 0, f"{i+1}: {item.name} (Damage: {item.damage})")
                elif isinstance(item, Potion):
                    if hasattr(item, 'health_restored'):
                        self.legend_window.addstr(17 + i, 0, f"{i+1}: {item.name} (Restores: {item.health_restored} HP)",curses.color_pair(3))
                    elif hasattr(item, 'mana_restored'):
                        self.legend_window.addstr(17 + i, 0, f"{i+1}: {item.name} (Restores: {item.mana_restored} MP)")
                    elif hasattr(item, 'strength_increase'):
                        self.legend_window.addstr(17 + i, 0,
                              f"{i+1}: {item.name} (Increases strength by {item.strength_increase}%)")
                else:
                    self.legend_window.addstr(16 + i, 0, f"{i+1}: {item.name}")

        # Display the messages
        for i, message in enumerate(self.message_log[-4:]):
            self.message_window.addstr(i, 0, message)

        # Refresh all windows
        self.game_window.refresh()
        self.message_window.refresh()
        self.legend_window.refresh()
        # self.status_window.refresh()

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

    game = Game()
    game.run()