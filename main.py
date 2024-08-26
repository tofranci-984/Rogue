import curses
import json
# import random
import pickle
import logging
import datetime
import random
import pygame


pygame.init()
pygame.mixer.init()

logger= logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logging.basicConfig(filename='log.txt', filemode='w', format='%(asctime)s %(message)s', level=logging.DEBUG)  # filemode= w will overwrite file each time


class Weapon:
    def __init__(self, name, damage, attack_range):
        self.name = name
        self.damage = damage
        self.attack_range = attack_range
        logger.debug(f"Creating weapon '{name}' with damage of {damage}")


class Enemy:
    def __init__(self, name, hp, damage, sense_range):
        self.name = name
        self.hp = hp
        self.damage = damage
        self.sense_range = sense_range
        logger.debug(f"Creating enemy {name} with {hp} HP and damage of {damage}")


class Player:
    def __init__(self, name, hp, weapons, gold=0):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.weapon = weapons[0]    # default weapon
        self.gold = gold
        self.mana = 5
        self.max_mana = self.mana
        self.strength = 10
        self.dexterity = 10
        self.max_strength = self.strength
        self.max_dexterity = self.dexterity

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
        self.height, self.width = self.screen.getmaxyx()
        self.player = None
        self.enemies = []
        self.weapons = []
        self.level = 2
        self.event_log = []

        # Load weapon and enemy data
        self.load_weapons()
        self.load_enemies()

        # Initialize level variables
        self.level_width = 40
        self.level_height = 20
        self.grid = []
        self.entry_point = (0, 0)
        self.exit_point = (0, 0)
        self.message = ""
        self.show_debug_info = True

        # Load level data
        level_data = self.load_level()
        if level_data:
            self.level_width = level_data['width']
            self.level_height = level_data['height']
            self.grid = [list(row) for row in level_data['grid']]
            self.entry_point = level_data['entry_point']
            self.exit_point = level_data['exit_point']
        else:
            logger.error("Failed to load level data")
            self.message = "Error: Failed to load level data"

        # Initialize color pairs
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Walls
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Start and Exit
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)  # Monsters
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Player
        curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Player and Gold

        # Place player at entry point
        self.player_pos = self.entry_point
        self.grid[self.player_pos[1]][self.player_pos[0]] = '@'

        # Load sound effects
        self.volume = 0.5  # Default volume (50%)
        self.gold_sound = pygame.mixer.Sound("sounds/coin.wav")
        self.enemy_sound = pygame.mixer.Sound("sounds/heal.wav")

        # set viewport coords to 0
        self.viewport_y = 0
        self.viewport_x = 0

    def calculate_viewport(self):
        player_y, player_x = self.player_pos
        self.viewport_y = max(0, min(player_y - self.viewport_height // 2, self.level_height - self.viewport_height))
        self.viewport_x = max(0, min(player_x - self.viewport_width // 2, self.level_width - self.viewport_width))

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))  # Ensure volume is between 0 and 1
        # self.move_sound.set_volume(self.volume)
        self.gold_sound.set_volume(self.volume)
        self.enemy_sound.set_volume(self.volume)

    def increase_volume(self):
        self.set_volume(self.volume + 0.1)
        self.message = f"Volume increased to {int(self.volume * 100)}%"

    def decrease_volume(self):
        self.set_volume(self.volume - 0.1)
        self.message = f"Volume decreased to {int(self.volume * 100)}%"

    def move_player(self, dy, dx):
        new_y = self.player_pos[1] + dy
        new_x = self.player_pos[0] + dx
        self.calculate_viewport()

        if 0 <= new_y < self.level_height and 0 <= new_x < self.level_width:
            new_cell = self.grid[new_y][new_x]
            logger.debug(f"new_cell={new_cell}, dy={dy}, dx={dx}, new_y={new_y}, new_x={new_x}")

            # Check for adjacent monsters
            monster_adjacent = False
            for y in range(max(0, new_y - 1), min(self.level_height, new_y + 2)):
                for x in range(max(0, new_x - 1), min(self.level_width, new_x + 2)):
                    if self.grid[y][x] == 'M':  # player is moving near or on Enemy
                        logger.debug(f"Enemy in range!, dy={dy}, dx={dx}, new_y={new_y}, new_x={new_x}, y={y}, x={x}")

                        if (new_cell != 'M'):  # prevent being in same cell as enemy
                            self.grid[self.player_pos[1]][self.player_pos[0]] = '.'
                            self.grid[new_y][new_x] = '@'
                            self.player_pos = (new_x, new_y)
                            self.message = "Enemy is in range! Prepare to fight!"
                            monster_adjacent = True
                            self.enemy_sound.play()
                            break

                        # Add combat logic here
                        return

            if new_cell == '.' or new_cell == '@':
                # Move to empty space or current position
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace with blank
                self.grid[new_y][new_x] = '@'
                self.player_pos = (new_x, new_y)
                self.message = "You moved."
            elif new_cell == '#':
                self.message = "You bumped into a wall."
            elif new_cell == 'G':
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace gold with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = (new_x, new_y)
                self.message = "You have found treasure!"
                self.gold_sound.play()
                # insert treasure logic here
                self.player.gold += random.randint(1,100)
            elif new_cell == '^':   # trap
                self.grid[self.player_pos[1]][self.player_pos[0]] = '.'  # replace gold with blank
                self.grid[new_y][new_x] = '!'
                self.player_pos = (new_x, new_y)
                hp = random.randint(1,int(self.player.hp/3))
                self.player.hp -= random.randint(1,int(self.player.hp/3))
                self.message = f"You have triggered a trap!  You suffered {hp} damage!"
                self.enemy_sound.play()
                self.player.hp -= hp
                if self.player.hp <= 0:
                    self.message = "You have been defeated by the monster!"
                    self.game_over = True

                # insert trap logic here
            elif new_cell == 'E':
                self.message = "You found the exit!"
                # Add level completion logic here
            else:
                logger.debug(f"Unknown object encountered {new_cell} at new_y:{new_y}, new_x:{new_x}")
                self.message = f"You encountered an unknown object: {new_cell}"

        # self.calculate_viewport()

    def load_weapons(self):
        with open('game/weapons.json') as f:
            weapons_data = json.load(f)
        for weapon in weapons_data:
            self.weapons.append(Weapon(**weapon))

    def load_enemies(self):
        with open('game/enemies.json') as f:
            enemies_data = json.load(f)
        for enemy in enemies_data:
            self.enemies.append(Enemy(**enemy))

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
            self.message = f"Level {self.level} loaded successfully"
            logger.debug(
                f"Level data: width={self.level_width}, height={self.level_height}, grid size={len(self.grid)}x{len(self.grid[0]) if self.grid else 0}")
            return level_data
        except FileNotFoundError:
            logger.error(f"File {filename} not found")
            self.message = f"Error: Level {self.level} not found"
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {filename}")
            self.message = f"Error: Invalid level data for level {self.level}"
        except Exception as e:
            logger.error(f"Unexpected error loading level: {str(e)}")
            self.message = f"Error: Failed to load level {self.level}"
        return None

    def save_game(self):
        logger.debug("save_game()")
        with open('savegame.pkl', 'wb') as f:
            pickle.dump((self.player, self.enemies, self.level), f)

    def load_game(self):
        logger.debug("load_game()")
        with open('savegame.pkl', 'rb') as f:
            self.player, self.enemies, self.level = pickle.load(f)

    def show_stats(self):
        # Logic for displaying player stats
        pass

    def show_event_log(self):
        # Logic for displaying event log
        pass

    def show_automap(self):
        # Logic for displaying automap
        pass

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
            self.message = "Debug info toggled"

        return True

    def update(self):
        self.screen.clear()
        max_y, max_x = self.screen.getmaxyx()

        # Calculate available space for legend
        self.legend_width = 20  # Adjust this value based on your legend's content
        self.viewport_width = self.width - self.legend_width - 1 # -1 for the border
        self.viewport_height = self.height - 1 # -1 for the message bar at the bottom

        self.viewport_x = 0
        self.viewport_y = 0

        available_width = max_x - self.level_width
        legend_start_x = min(self.level_width, max_x - self.legend_width)

        # Print the visible portion of the level
        for y in range(self.viewport_height):
            for x in range(self.viewport_width):
                level_y = y + self.viewport_y
                level_x = x + self.viewport_x
                if 0 <= level_y < self.level_height and 0 <= level_x < self.level_width:
                    cell = self.grid[level_y][level_x]
                    try:
                        if cell == '#':
                            self.screen.addch(y, x, cell, curses.color_pair(1))
                        elif cell in ['S', 'E']:
                            self.screen.addch(y, x, cell, curses.color_pair(2))
                        elif cell == 'M':
                            self.screen.addch(y, x, cell, curses.color_pair(3))
                        elif cell in ['@']:
                            self.screen.addch(y, x, cell, curses.color_pair(5))
                        elif cell in ['G']:
                            self.screen.addch(y, x, '*', curses.color_pair(4))
                        else:
                            self.screen.addch(y, x, cell)
                    except curses.error:
                        pass

        # Draw border between level and legend
        for y in range(self.viewport_height):
            self.screen.addch(y, self.viewport_width, '|')

            # Print the legend
            legend_start_x = self.viewport_width + 1
            if self.show_debug_info:
                debug_info = f"Player: ({self.player_pos[0]}, {self.player_pos[1]})"
                debug_info += f" Viewport: ({self.viewport_x}, {self.viewport_y})"
                self.screen.addstr(0, legend_start_x, debug_info[:self.legend_width])

            self.screen.addstr(1, legend_start_x, "Legend:")
            legend_entries = [
                ("#", "Wall", 1),
                ("S/E", "Start/Exit", 2),
                ("M", "Monster", 3),
                ("@", "Player", 5),
                (f"{self.player.gold}", "Gold", 4)
            ]
            for i, (symbol, description, color) in enumerate(legend_entries):
                if 2 + i < self.viewport_height:
                    self.screen.addstr(2 + i, legend_start_x, symbol, curses.color_pair(color))
                    self.screen.addstr(2 + i, legend_start_x + 2, f"- {description}"[:self.legend_width - 2])

            # Display player stats
        stats = [
            ("HP", self.player.hp, self.player.max_hp),
            ("Mana", self.player.mana, self.player.max_mana),
            ("Strength", self.player.strength, self.player.max_strength),
            ("Dexterity", self.player.dexterity, self.player.max_dexterity)
        ]
        for i, (label, value, max_value) in enumerate(stats):
            if 9 + i < self.viewport_height:
                color = 2 if value >= max_value * 0.25 else 3
                stat_str = f"{value}/{max_value} - {label}"
                self.screen.addstr(9 + i, legend_start_x, stat_str[:self.legend_width], curses.color_pair(color))

        # Display player items
        for i, weapon in enumerate(self.player.items):
            if 14 + i < self.viewport_height:
                if isinstance(weapon, Weapon):
                    item_str = f"{weapon.name}: Dmg {weapon.damage}, Range {weapon.attack_range}"
                else:
                    item_str = f"Unknown item: {weapon}"
                self.screen.addstr(14 + i, legend_start_x, item_str[:self.legend_width])

        # Display the message
        try:
            self.screen.addstr(max_y - 1, 0, self.message[:max_x - 1])
        except curses.error:
            pass

        self.calculate_viewport()


    def render(self):
        # self.screen.clear()
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
