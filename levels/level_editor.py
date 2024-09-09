import curses
import json
import os
import readline

MAX_LEVEL_WIDTH = 200
MAX_LEVEL_HEIGHT = 200

class LevelEditor:
    def __init__(self, screen):
        self.screen = screen
        self.height, self.width = screen.getmaxyx()
        self.level_width = 40
        self.level_height = 20
        self.grid = [['.' for _ in range(self.level_width)] for _ in range(self.level_height)]
        self.entry_point = None
        self.exit_point = None
        self.cursor_y, self.cursor_x = 0, 0
        self.message = ""
        self.paint_mode = False
        self.paint_tile = '.'
        self.filename = ""
        self.level_extension = ".lvl"

    def draw_screen(self):
        self.screen.clear()
        max_y, max_x = self.screen.getmaxyx()

        # Draw grid
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if y == self.cursor_y and x == self.cursor_x:
                    self.screen.addch(y, x, cell, curses.A_STANDOUT)  # Highlight the cursor position
                else:
                    self.screen.addch(y, x, cell)

        # Draw legend
        legend_x = min(self.level_width + 2, max_x - 40)  # Ensure legend fits on screen
        legend_items = [
            "Legend:",
            f"Cursor: {self.cursor_y}, {self.cursor_x}",
            ". - Floor",
            "# - Wall",
            "+ - Door",
            "^ - Trap",
            "@ - Entry",
            "X - Exit",
            "E - Enemy",
            "$ - Gold",
            "< - Stairs Up",
            "> - Stairs Down",
            "T - Treasure",
            "P - RandomPotion",
            "M - Mana Potion",
            "H - Healing Potion",
            "R - Resize level",
            "",
            "Arrow keys: Move",
            "Space: Place tile",
            "P: Toggle paint mode",
            "S: Save",
            "L: Load",
            "Q: Quit",
            "",
            f"Paint mode: {'ON' if self.paint_mode else 'OFF'}",
            "",
            f"Paint tile: {self.paint_tile}",
            ""
        ]

        column1_items = legend_items[::2]
        column2_items = legend_items[1::2]

        for i, (text1, text2) in enumerate(zip(column1_items, column2_items)):
            if i < max_y - 1:
                self.screen.addnstr(i, legend_x, text1, max_x - legend_x - 1)
                self.screen.addnstr(i, legend_x + 21, text2, max_x - legend_x - 1)

        # Draw message at the bottom
        # if max_y > 2:
        #     self.screen.addnstr(max_y - 2, 0, self.message, max_x - 1)

        self.screen.addnstr(22, 0, self.message, max_x - 1)

        # Move cursor
        if self.cursor_y < max_y - 1 and self.cursor_x < max_x - 1:
            self.screen.move(self.cursor_y, self.cursor_x)

        self.screen.refresh()

    def set_tile(self, tile):
        if 0 <= self.cursor_y < self.level_height and 0 <= self.cursor_x < self.level_width:
            self.grid[self.cursor_y][self.cursor_x] = tile
            if tile == '@':
                self.entry_point = [self.cursor_x, self.cursor_y]
            elif tile == 'X':
                self.exit_point = [self.cursor_x, self.cursor_y]

    def save_level(self, filename):
        entry_point = []
        # entry_point.append(self.entry_point)

        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if cell == '@':
                    entry_point.append( [x, y])
        if not entry_point:
            self.message = "No entry point found"
            return

        if len(entry_point) > 1:
            self.message = f"Multiple entry points found\n{entry_point}"
            return

        level_data = {
            "width": self.level_width,
            "height": self.level_height,
            "entry_point": self.entry_point,
            "exit_point": self.exit_point,
            "grid": [
                "".join(row) for row in self.grid
            ]
        }
        with open(filename, 'w') as f:
            json.dump(level_data, f, indent=2, sort_keys=True)
        self.message = f"Level saved to \"{filename}\""

    def load_level(self, filename):
        try:
            with open(filename, 'r') as f:
                level_data = json.load(f)
            self.level_width = level_data['width']
            self.level_height = level_data['height']
            self.grid = [list(row) for row in level_data['grid']]
            self.entry_point = level_data['entry_point']
            self.exit_point = level_data['exit_point']
            self.message = f"Level loaded from {filename}"
        except FileNotFoundError:
            self.message = f"File \"{filename}\" not found"
        except json.JSONDecodeError:
            self.message = f"Invalid JSON in {filename}"

def main(screen):
    curses.curs_set(1)  # Show cursor
    editor = LevelEditor(screen)
    filename = ""

    while True:
        editor.draw_screen()
        screen.addstr(editor.level_height + 1, 0, "Enter command: ")  # Print prompt below level grid
        screen.refresh()
        key = screen.getch()  # Get input from user

        if key == ord('q'):
            break
        elif key == ord('p'):
            editor.paint_mode = not editor.paint_mode
            editor.message = f"Paint mode {'enabled' if editor.paint_mode else 'disabled'}"
        elif key == ord('s'): # save level
            files = [f for f in os.listdir('.') if f.endswith('.lvl')]
            if not files:
                editor.message = "No .lvl files found. Enter filename to save: "
            else:
                editor.message = "Save Level"
                screen.clear()  # clear the screen
                screen.addstr(1, 1, "Select a file to save as, or enter a new filename:")  # print the prompt
                files=sorted(files)
                for i, file in enumerate(files):
                    screen.addstr(i + 2, 1, f"{i + 1}. {file}")  # print the file list
                screen.addstr(len(files) + 3, 1, "Enter filename or number (Q to cancel): ")  # print the input prompt
                screen.refresh()  # update the screen
                curses.echo()
                choice = screen.getstr().decode('utf-8')
                if choice.upper() == 'Q':
                    editor.message = "Save cancelled"
                    editor.draw_screen()  # redraw the editor screen
                elif choice.isdigit() and 1 <= int(choice) <= len(files):
                    filename = files[int(choice) - 1]
                else:
                    filename = choice
                if not filename.endswith('.lvl'):
                    filename += '.lvl'
                curses.noecho()
                screen.addstr(len(files) + 4, 1, f"You have selected to save the file as: {filename}")
                screen.refresh()
                screen.addstr(len(files) + 5, 1, "Is this correct? (y/n): ")
                screen.refresh()
                curses.echo()
                response = screen.getstr(len(files) + 5, 24).decode('utf-8')
                screen.refresh()
                if response.upper() == "Y":
                    editor.save_level(filename)
                else:
                    screen.addstr(len(files) + 6, 1, "Save cancelled")
                editor.draw_screen()  # redraw the editor screen
        elif key == ord('l'): # load level
            files = [f for f in os.listdir('.') if f.endswith('.lvl')]
            if not files:
                editor.message = "No .lvl files found. Enter filename to load: "
            else:
                editor.message = "Load Level"
                screen.clear()  # clear the screen
                screen.addstr(1, 1, "Select a file to load, or enter a new filename:")  # print the prompt
                files=sorted(files)
                for i, file in enumerate(files):
                    screen.addstr(i + 2, 1, f"{i + 1}. {file}")  # print the file list
                screen.addstr(len(files) + 3, 1, "Enter filename or number (Q to cancel): ")  # print the input prompt
                screen.refresh()  # update the screen
                curses.echo()
                choice = screen.getstr().decode('utf-8')
                if choice.upper() == 'Q':
                    editor.message = "Load cancelled"
                    editor.draw_screen()  # redraw the editor screen
                elif choice.isdigit() and 1 <= int(choice) <= len(files):
                    filename = files[int(choice) - 1]
                    editor.load_level(filename)
                    screen.move(0, 0)
                else:
                    filename = choice
                    editor.load_level(filename)
                    screen.move(0, 0)

                curses.noecho()
                editor.draw_screen()  # redraw the editor screen
        elif key == ord('r'):
            screen.addstr(editor.level_height + 1, 0, "Enter new width: ")
            screen.refresh()
            curses.echo()
            new_width = screen.getstr(editor.level_height + 1, 15).decode('utf-8')
            screen.addstr(editor.level_height + 1, 0, "Enter new height: ")
            screen.refresh()
            new_height = screen.getstr(editor.level_height + 1, 16).decode('utf-8')

            # Resize the level
            if int(new_width) > editor.level_width:
                for row in editor.grid:
                    row.extend(['.'] * (int(new_width) - editor.level_width))
            elif int(new_width) < editor.level_width:
                for row in editor.grid:
                    row[:] = row[:int(new_width)]

            if int(new_height) > editor.level_height:
                editor.grid.extend([['.'] * int(new_width) for _ in range(int(new_height) - editor.level_height)])
            elif int(new_height) < editor.level_height:
                editor.grid[:] = editor.grid[:int(new_height)]

            editor.level_width = int(new_width)
            editor.level_height = int(new_height)
        elif key == ord('i'):
            screen.clear()
            editor.message = "Enter tile type (. # + ^ @ $ E X P H M G T < >): "
            editor.draw_screen()
            curses.echo()
            tile = str(chr(screen.getch()).upper())
            curses.noecho()
            if tile in '.#+^@$EXPHMGT<>':
                editor.paint_tile = tile
            editor.message = f"Selected tile: {tile}"
            editor.draw_screen()  # redraw the screen to remove the input prompt
        elif key == ord(' '):
            if 0 <= editor.cursor_y < editor.level_height and 0 <= editor.cursor_x < editor.level_width:
                editor.set_tile(editor.paint_tile)
            editor.message = f"Placed tile: {editor.paint_tile}"
            editor.draw_screen()  # redraw the screen to remove the input prompt
        elif key == curses.KEY_UP and editor.cursor_y > 0:
            editor.cursor_y -= 1
        elif key == curses.KEY_DOWN and editor.cursor_y < editor.level_height - 1:
            editor.cursor_y += 1
        elif key == curses.KEY_LEFT and editor.cursor_x > 0:
            editor.cursor_x -= 1
        elif key == curses.KEY_RIGHT and editor.cursor_x < editor.level_width - 1:
            editor.cursor_x += 1

        # Paint mode: place tile if paint mode is on
        if editor.paint_mode:
            editor.set_tile(editor.paint_tile)

    # Clear the screen before exiting
    screen.clear()
    screen.refresh()


if __name__ == "__main__":
    curses.wrapper(main)