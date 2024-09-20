import curses
from curses import wrapper
import json
import pickle
import logging
import random
import pygame
import os

pygame.init()
pygame.mixer.init()

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logging.basicConfig(filename='log.txt', filemode='w', format='%(asctime)s %(message)s',
                    level=logging.DEBUG)  # filemode= w will overwrite file each time

# Define the level-up experience points (total, not additional)
level_up_experience = [
    20, 50, 100, 200, 300, 400, 500, 600, 700, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000
]

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

    def level_up(self):
        self.level += 1
        self.max_hp += 10
        self.hp = min(self.hp + 10, self.max_hp)
        self.max_mana += 5
        self.mana = min(self.mana + 5, self.max_mana)
        self.strength += 5
        self.dexterity += 5
        self.max_strength = self.strength
        self.max_dexterity = self.dexterity

    def check_level_up(self):
        for level, experience in enumerate(level_up_experience):
            if self.xp >= experience and self.level <= level + 1:
                self.level_up()
                return True

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
        self.terminal_height, self.terminal_width = curses.LINES, curses.COLS
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
        self.message_log = []

        self.combat_window = curses.newwin(self.viewport_height - 2, self.viewport_width , 0, 0)
        self.combat_window.scrollok(True)
        self.combat_messages = []
        self.combat_message_log = []

        # Load weapon and enemy data
        self.load_weapons()
        self.load_enemies()

        # Load level data
        level_data = self.load_level()

        # Generate level
        self.generate_level(self.level_width, self.level_height, 3, 10, 10, 5)

        if level_data:
            if 'entry_point' in level_data:
                self.player_pos = list(level_data['entry_point'])  # this may be outside the viewport
            else:
                logger.error("Entry point not found in level data")
                self.add_message("Error: Entry point not found in level data")
                self.game_over = True
            self.grid[int(self.player_pos[1])][int(self.player_pos[0])] = '@'
        else:
            logger.error("Failed to load level data")
            self.add_message("Error: Failed to load level data")

        # Populate level with enemies and items
        self.populate_level(10, 10, 10, 10)

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

    def distance(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def populate_level(self, num_enemies, num_potions, num_gold, num_items):
        floor_cells = [(y, x) for y, row in enumerate(self.grid) for x, cell in enumerate(row) if cell == '.']
        num_floor_cells = len(floor_cells)

        # Ensure there are enough floor cells for placement
        if num_enemies + num_potions + num_gold + num_items > num_floor_cells:
            raise ValueError("Not enough floor cells to place all items")

        # Create sets to store the coordinates of placed items
        enemy_cells = set()
        potion_cells = set()
        gold_cells = set()
        item_cells = set()

        # Add enemies, potions, and items
        for _ in range(num_enemies):
            enemy_cell = random.choice(floor_cells)
            floor_cells.remove(enemy_cell)
            if 0 <= enemy_cell[0] < len(self.grid[0]) and 0 <= enemy_cell[1] < len(self.grid):
                self.grid[enemy_cell[1]][enemy_cell[0]] = 'E'
                enemy_cells.add(enemy_cell)

        for _ in range(num_potions):
            potion_cell = random.choice(floor_cells)
            floor_cells.remove(potion_cell)
            if 0 <= potion_cell[0] < len(self.grid[0]) and 0 <= potion_cell[1] < len(self.grid):
                self.grid[potion_cell[1]][potion_cell[0]] = random.choice(
                    ['H', 'M'])  # H for health potion, M for mana potion
                potion_cells.add(potion_cell)

        for _ in range(num_gold):
            gold_cell = random.choice(floor_cells)
            floor_cells.remove(gold_cell)
            if 0 <= gold_cell[0] < len(self.grid[0]) and 0 <= gold_cell[1] < len(self.grid):
                self.grid[gold_cell[1]][gold_cell[0]] = '$'
                gold_cells.add(gold_cell)

        for _ in range(num_items):
            item_cell = random.choice(floor_cells)
            floor_cells.remove(item_cell)
            if 0 <= item_cell[0] < len(self.grid[0]) and 0 <= item_cell[1] < len(self.grid):
                # add a random item from the list of items


                item_cells.add(item_cell)

        # Ensure the player is not too close to any items
        for item_cell in item_cells:
            if self.distance(self.player_pos, item_cell) < 3:
                item_cells.remove(item_cell)
                floor_cells.remove(item_cell)
                new_item_cell = random.choice(floor_cells)
                self.grid[new_item_cell[1]][new_item_cell[0]] = self.grid[item_cell[1]][item_cell[0]]
                floor_cells.remove(new_item_cell)
                self.grid[item_cell[1]][item_cell[0]] = '.'

        # Add the remaining items to the level
        for item_cell in item_cells:
            self.grid[item_cell[1]][item_cell[0]] = self.grid[item_cell[1]][item_cell[0]].capitalize()

        # Ensure the player is not too close to any potions
        for potion_cell in potion_cells:
            if self.distance(self.player_pos, potion_cell) < 3:
                potion_cells.remove(potion_cell)
                floor_cells.remove(potion_cell)
                new_potion_cell = random.choice(floor_cells)
                self.grid[new_potion_cell[1]][new_potion_cell[0]] = self.grid[potion_cell[1]][potion_cell[0]]
                floor_cells.remove(new_potion_cell)
                self.grid[potion_cell[1]][potion_cell[0]] = '.'

        # Add the remaining potions to the level
        for potion_cell in potion_cells:
            self.grid[potion_cell[1]][potion_cell[0]] = self.grid[potion_cell[1]][potion_cell[0]].capitalize()

        # Ensure the player is not too close to any gold
        for gold_cell in gold_cells:
            if self.distance(self.player_pos, gold_cell) < 3:
                gold_cells.remove(gold_cell)
                floor_cells.remove(gold_cell)
                new_gold_cell = random.choice(floor_cells)
                self.grid[new_gold_cell[1]][new_gold_cell[0]] = self.grid[gold_cell[1]][gold_cell[0]]
                floor_cells.remove(new_gold_cell)
                self.grid[gold_cell[1]][gold_cell[0]] = '.'

        # Add the remaining gold to the level
        for gold_cell in gold_cells:
            self.grid[gold_cell[1]][gold_cell[0]] = self.grid[gold_cell[1]][gold_cell[0]].capitalize()

        # Ensure the player is not too close to any enemies
        for enemy_cell in enemy_cells:
            if self.distance(self.player_pos, enemy_cell) < 3:
                enemy_cells.remove(enemy_cell)
                floor_cells.remove(enemy_cell)
                new_enemy_cell = random.choice(floor_cells)
                self.grid[new_enemy_cell[1]][new_enemy_cell[0]] = self.grid[enemy_cell[1]][enemy_cell[0]]
                floor_cells.remove(new_enemy_cell)
                self.grid[enemy_cell[1]][enemy_cell[0]] = '.'

        # Add the remaining enemies to the level
        for enemy_cell in enemy_cells:
            self.grid[enemy_cell[1]][enemy_cell[0]] = self.grid[enemy_cell[1]][enemy_cell[0]].capitalize()

    def generate_level(self, width, height, num_rooms, num_enemies, num_potions, num_items):
        def create_room(x, y, w, h):
            for i in range(x, x + w):
                for j in range(y, y + h):
                    self.grid[j][i] = '.'

        def add_door(x, y, w, h):
            doors = 0
            if random.random() < 0.5 and x > 1:
                self.grid[y][x - 2] = '+'
                doors += 1
                self.grid[y][x - 1] = '.'
            if random.random() < 0.5 and x < w - 2:
                self.grid[y][x + 2] = '+'
                doors += 1
                self.grid[y][x + 1] = '.'
            if random.random() < 0.5 and y > 1:
                self.grid[y - 2][x] = '+'
                doors += 1
                self.grid[y - 1][x] = '.'
            if random.random() < 0.5 and y < h - 2:
                self.grid[y + 2][x] = '+'
                doors += 1
                self.grid[y + 1][x] = '.'
            return doors

        def connect_rooms(room1, room2):
            if room1[0] < room2[0]:
                self.grid[room1[1] + room1[3] - 1][room1[0] + room1[2]] = '.'
                self.grid[room2[1]][room2[0] - 1] = '.'
            else:
                self.grid[room1[1]][room1[0] - room1[2] + 1] = '.'
                self.grid[room2[1] + room2[3]][room2[0] + room2[2]] = '.'

        self.grid = []
        for _ in range(height):
            self.grid.append(['#' for _ in range(width)])

        # Add rooms
        rooms = []
        while len(rooms) < num_rooms:
            room_width = random.randint(5, 15)
            room_height = random.randint(5, 15)
            room_x = random.randint(0, width - room_width - 1)
            room_y = random.randint(0, height - room_height - 1)
            room_overlaps = False
            for room in rooms:
                if (room_x < room[0] + room[2] and
                        room_x + room_width > room[0] and
                        room_y < room[1] + room[3] and
                        room_height + room_y > room[1]):
                    room_overlaps = True
                    break
            if not room_overlaps:
                create_room(room_x, room_y, room_width, room_height)
                doors = add_door(room_x, room_y, room_width, room_height)
                rooms.append((room_x, room_y, room_width, room_height, doors))

        # Add stairs up and down
        stairs_placed = False
        while not stairs_placed:
            stair_room_index = random.randint(0, num_rooms - 1)
            if rooms[stair_room_index][4] > 0:
                stair_x = rooms[stair_room_index][0] + random.randint(0, rooms[stair_room_index][2] - 1)
                stair_y = rooms[stair_room_index][1] + random.randint(0, rooms[stair_room_index][3] - 1)
                if self.grid[stair_y][stair_x] == '.':
                    self.grid[stair_y][stair_x] = '<'
                    self.entry_point = (stair_x, stair_y)
                    stairs_placed = True

        # Connect rooms
        for i in range(num_rooms):
            for j in range(i + 1, num_rooms):
                if random.random() < 0.5 and not rooms[i][0] < rooms[j][0] + rooms[j][2] - 3 and \
                        not rooms[i][0] + rooms[i][2] > rooms[j][0] + 3 and \
                        not rooms[i][1] < rooms[j][1] + rooms[j][3] - 3 and \
                        not rooms[i][1] + rooms[i][3] > rooms[j][1] + 3:
                    connect_rooms(rooms[i], rooms[j])

        # Add passages
        for i in range(num_rooms):
            for j in range(i + 1, num_rooms):
                if random.random() < 0.5 and not rooms[i][0] < rooms[j][0] + rooms[j][2] - 3 and \
                        not rooms[i][0] + rooms[i][2] > rooms[j][0] + 3 and \
                        not rooms[i][1] < rooms[j][1] + rooms[j][3] - 3 and \
                        not rooms[i][1] + rooms[i][3] > rooms[j][1] + 3:
                    self.grid[rooms[i][1] + random.randint(0, rooms[i][3] - 1)] \
                        [rooms[i][0] + random.randint(0, rooms[i][2] - 1)] = '.'
                    self.grid[rooms[j][1] + random.randint(0, rooms[j][3] - 1)] \
                        [rooms[j][0] + random.randint(0, rooms[j][2] - 1)] = '.'

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

    def update_combat_message_window(self):
        max_width = self.combat_window.getmaxyx()[1]
        max_height = self.combat_window.getmaxyx()[0] - 2
        lines = []
        combat_message_window_height = self.viewport_height - 4 # Subtract 1 for the title line
        for i, message in enumerate(self.combat_message_log[-combat_message_window_height:]):
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

        self.combat_window.clear()
        self.combat_window.erase()
        self.combat_window.box()
        self.combat_window.addstr(0, 2, "[ Combat Log ]", curses.color_pair(3))

        max_width= self.combat_window.getmaxyx()[1] - 2
        total_lines = len(lines)
        for i, (line, attrs) in enumerate(lines):
            logger.debug(
                f"line: {line}, attrs: {attrs}, total_lines: {total_lines}, i: {i}, max_height: {max_height}, max_width: {max_width}")
            self.combat_window.addnstr(i + 1, 1, line, max_width, attrs)
        self.combat_window.refresh()

    def add_message(self, message, message_window_height=4):
        """
        Add a message to the message log.
        """
        self.message_log.append(message)
        logger.debug(f"{message}")
        self.message_window.erase()
        self.update_message_window(message_window_height)
    def add_combat_message(self, message, message_window_height=10):
        self.combat_message_log.append(message)
        logger.debug(f"{message}")
        self.update_combat_message_window()

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
                            # create combat window
                            eligible_enemies = [enemy for enemy in self.enemies if enemy.level <= self.player.level]
                            if eligible_enemies:
                                enemy = random.choice(eligible_enemies)
                            else:
                                # Handle the case where there are no enemies at or below the player's level
                                # For example, you could add a message to the player or choose an enemy at a higher level
                                logger.debug(f"No enemies at or below your level!: LVL={self.player.level}")
                                enemy = random.choice(self.enemies)  # Choose a random enemy

                            self.combat_window.erase()
                            self.combat_window.box()
                            self.combat_window.addstr(0, 2, "[ Combat Log ]", curses.color_pair(3))
                            self.combat_window.refresh()

                            while self.player.hp > 0 and enemy.hp > 0:
                                self.add_combat_message(f"You are in range of a {enemy.name} ({enemy.hp}/{enemy.start_hp})!")
                                self.add_combat_message("Do you want to (A)ttack or (F)lee? ")
                                key = -1
                                while key == -1:
                                    key = self.screen.getch()

                                if key == ord('a'):
                                    # Player attacks
                                    min_damage = 1 + self.player.level + (self.player.strength // 4)
                                    max_damage = min_damage + round(self.player.weapon.damage * (1+(self.player.strength/100)))
                                    attack_damage = random.randint(min_damage, max_damage)
                                    enemy.hp -= attack_damage
                                    self.add_combat_message(
                                        f"You attack {enemy.name} for {attack_damage} damage.")
                                    self.add_combat_message(f"{enemy.name} HP ({enemy.hp}/{enemy.start_hp})")
                                    if self.soundON:
                                        self.enemy_sound.play()

                                    if enemy.hp <= 0:
                                        self.add_combat_message(f"You defeated the {enemy.name}!")
                                        self.add_message(f"You defeated the {enemy.name}!")
                                        self.enemies.remove(enemy)
                                        self.grid[y][x] = '.'  # clear the enemy cell
                                        self.game_window.refresh()
                                        self.add_combat_message(f"You gained {enemy.xp} XP!")
                                        self.add_message(f"You gained {enemy.xp} XP!")
                                        self.player.xp += enemy.xp

                                        # Check if player levelled up
                                        if self.player.check_level_up():
                                            self.add_message(f"You are now level {self.player.level}!")
                                            self.add_message(f"Check your new stats!")
                                            self.legend_window.erase()
                                            self.legend_window.clear()
                                            self.legend_window.refresh()
                                            self.update()

                                        # add random gold to player based on monster level
                                        gold = random.randint(self.player.level, enemy.level * 10)
                                        self.add_combat_message(f"{enemy.name} dropped {gold} gold!")
                                        self.add_combat_message(f"Press a key to exit combat")
                                        # get input to exit combat window
                                        key = -1
                                        while key == -1:
                                            key = self.screen.getch()
                                        self.add_combat_message(f"\n")
                                        break

                                    # Enemy attacks
                                    # add a random dexterity test for avoiding enemy attacks.
                                    # As dex increases, chance of avoiding increases
                                    dex_check= random.randint(self.player.dexterity, 100)
                                    if dex_check > 50:
                                        # Player dodges the attack
                                        self.add_combat_message(f"You dodge the attack from the {enemy.name}!")
                                    else:  # Player is hit
                                        logger.debug(f"enemy level={enemy.level}, enemy damage={enemy.damage}, player level={self.player.level}, ")
                                        attack_damage = random.randint(1 + enemy.level, enemy.damage)
                                        logger.debug(f"attack damage={attack_damage}")
                                        self.player.hp -= attack_damage
                                        self.add_combat_message(f"{enemy.name} attacks you for {attack_damage} damage.")

                                    self.legend_window.erase()
                                    self.legend_window.clear()
                                    self.legend_window.refresh()
                                    self.update()

                                    if self.soundON:
                                        self.enemy_sound.play()

                                    if self.player.hp <= 0:
                                        self.add_combat_message(f"You have been defeated by the {enemy.name}!")
                                        self.game_over = True
                                        break
                                elif key == ord('f'):
                                    # Player flees
                                    self.add_message("You attempt to flee!", 20)
                                    self.add_message(
                                        "Which direction do you want to move? (N)orth, (S)outh, (E)ast, (W)est? ", 20)
                                    self.screen.refresh()
                                    key = -1
                                    while key == -1:
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

                        if monster_adjacent:
                            # try removing this line
                            # self.update_combat_message_window()
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
        elif key == ord('1'):
            self.view_message_log()
        elif key == ord('2'):
            self.legend_window.erase()
            self.legend_window.refresh()
            self.change_weapon()
        elif key == ord('?'):  # help menu
            self.show_help_menu()
            key = -1
            while key == -1:
                key = self.screen.getch()

            self.help_window.erase()
            self.help_window.refresh()

        elif key == ord('S'):  # Shift-D (capital S in curses)
            self.show_debug_info = not self.show_debug_info
            self.add_message("Debug info toggled")

        self.screen.nodelay(False)  # turn off nodelay / non-blocking input
        curses.echo()
        return True

    def show_help_menu(self):
        self.help_window = curses.newwin(23, 30, 1, 5)  # message_window = curses.newwin(4, 40, 20, 0)
        self.help_window.scrollok(True)
        self.help_window.bkgd(" ", curses.color_pair(2))
        self.help_window.box()

        middle_col = self.help_window.getmaxyx()[1] // 2 - len("[ Help ]") // 2

        y = 1
        self.help_window.addstr(0, middle_col, "[ Help ]")

        commands = [
            ("<up>", "move up"),
            ("<down>", "move down"),
            ("<left>", "move left"),
            ("<right>", "move right"),
            ("s", "save game"),
            ("l", "load game"),
            ("h", "drink health potion"),
            ("m", "drink mana potion"),
            ("+", "increase volume"),
            ("-", "decrease volume"),
            ("1", "show message log"),
            ("2", "show combat log"),
            ("3", "change Weapon"),
            ("S", "toggle debug info"),
            ("?", "show this help"),
            ("q", "quit")
        ]

        for key, description in commands:
            y += 1
            key_color = curses.color_pair(4)  # Cyan color for keys
            desc_color = curses.color_pair(3)  # Another color for descriptions
            self.help_window.addstr(y, 3, key, key_color)
            self.help_window.addstr(" - ", curses.color_pair(2))
            self.help_window.addstr(description, desc_color)

        y = 21
        msg = "Press a key to continue"
        middle_col = self.help_window.getmaxyx()[1] // 2 - len(msg) // 2
        self.help_window.addstr(y, middle_col, msg)
        self.help_window.refresh()

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
            key = -1
            while key == -1:
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
        self.legend_window.clear()
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

def main(stdscr):
    logger.debug("Start main")
    game = Game()
    game.run()
    logger.debug("End main")

def main_wrapper():
    curses.wrapper(main)

if __name__ == "__main__":
    curses.wrapper(main)


