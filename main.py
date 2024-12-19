import sys
import sqlite3
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, QEvent
import keyboard
import os
import requests
import threading
from transformers import pipeline
from gpt2_model import get_suggestion  # Import the function

class TextExpanderApp(QMainWindow):
    def __init__(self):
        """
        Initializes the TextExpanderApp with a window title, size, and layout.

        This method does the following:
        1. Initializes the main window with a title and geometry.
        2. Initializes the database and loads existing shortcuts.
        3. Creates a vertical layout for the main widget with labels, input fields, a table, and a search bar.
        4. Connects the input fields to the typing timer and the fetch_suggestions method.
        5. Connects the add button to the add_shortcut method.
        6. Connects the search input to the filter_shortcuts method.
        7. Creates and starts a keyboard listener thread to listen for hotkeys.
        """
        super().__init__()
        self.setWindowTitle("Text Expander")
        self.setGeometry(100, 100, 600, 400)

        # Initialize variables
        self.suggestion = ""  # Initialize suggestion attribute
        self.init_database()
        self.generator = pipeline('text-generation', model='gpt2')

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Instruction label
        instruction_label = QLabel("Use Tab to accept suggestions")
        instruction_label.setStyleSheet("font-size: 14px; color: blue;")
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instruction_label)

        # Input fields
        input_layout = QHBoxLayout()
        
        # Shortcut input
        shortcut_layout = QVBoxLayout()
        shortcut_label = QLabel("Shortcut:")
        self.shortcut_input = QLineEdit()
        shortcut_layout.addWidget(shortcut_label)
        shortcut_layout.addWidget(self.shortcut_input)
        input_layout.addLayout(shortcut_layout)
        
        # Expansion input with overlay suggestion label
        expansion_layout = QVBoxLayout()
        expansion_label = QLabel("Expansion Text:")
        self.expansion_input = QLineEdit()
        self.expansion_input.installEventFilter(self)
        self.hint_label = QLabel(self.expansion_input)
        self.hint_label.setStyleSheet("color: red; background-color: transparent;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.hint_label.hide()
        
        expansion_layout.addWidget(expansion_label)
        expansion_layout.addWidget(self.expansion_input)
        input_layout.addLayout(expansion_layout)

        # Set up suggestions with a timer to delay the fetch
        self.typing_timer = QTimer()
        self.typing_timer.setSingleShot(True)
        self.typing_timer.timeout.connect(self.fetch_suggestions)

        # Connect textChanged to restart the timer and hide the hint label
        self.expansion_input.textChanged.connect(self.restart_timer)
        self.expansion_input.textChanged.connect(self.on_text_change)

        # Continue with additional UI setup as per your app
        
        # Add temporary checkbox and button in a container
        action_layout = QVBoxLayout()
        action_layout.addSpacing(20)
        
        # Create a horizontal layout for checkbox and button
        checkbox_button_layout = QHBoxLayout()
        
        # Add temporary checkbox
        self.temporary_checkbox = QCheckBox("Temporary")
        checkbox_button_layout.addWidget(self.temporary_checkbox)
        
        # Add button
        self.add_button = QPushButton("Add Shortcut")
        self.add_button.clicked.connect(self.add_shortcut)
        checkbox_button_layout.addWidget(self.add_button)
        
        action_layout.addLayout(checkbox_button_layout)
        input_layout.addLayout(action_layout)

        # Add input section to main layout
        layout.addLayout(input_layout)
        
        # Add search bar to filter shortcuts table by matches(empty means all shortcuts)
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search shortcuts or expansions...")
        self.search_input.textChanged.connect(self.filter_shortcuts)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Create table for showing shortcuts
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Shortcut", "Expansion", "Temporary", "Action"])
        
        # Set column stretch behavior
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)  # Shortcut column
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)  # Expansion column
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)  # Temporary column
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)  # Action column
        
        layout.addWidget(self.table)

        # Load all shortcuts
        self.all_shortcuts = []
                
        # Load existing shortcuts
        self.load_shortcuts()
        self.setup_shortcuts_in_listener()  # Add loaded shortcuts to the listener

        # Start the keyboard listener in a separate thread
        self.listener_thread = threading.Thread(target=self.start_keyboard_listener, daemon=True)
        self.listener_thread.start()

    def restart_timer(self):
        """Restarts the timer whenever text is changed, delaying the suggestion fetching."""
        self.typing_timer.start(1000)  # 1-second delay

    def on_text_change(self):
        """Hides the hint label when the user starts typing."""
        self.hint_label.hide()
        self.restart_timer()

    def fetch_suggestions(self):
        """Fetches autosuggestions using the GPT-2 model from gpt2_model.py."""
        input_text = self.expansion_input.text().strip()
        if not input_text:
            self.hint_label.hide()
            return

        # Generate suggestion using the imported get_suggestion function
        suggested_text = get_suggestion(input_text)

        if suggested_text:
            suggestion_words = suggested_text.split()
            last_word = input_text.split()[-1]

            # Find the first word in the generated text that starts with the last word of input
            next_word = next((word for word in suggestion_words if word.startswith(last_word) and word != last_word), None)

            if next_word:
                # Set the suggestion text and show the hint label
                self.suggestion = next_word[len(last_word):]
                self.hint_label.setText(self.suggestion)
                self.hint_label.show()

                # Calculate cursor position in the input field
                cursor_position = self.expansion_input.cursorPosition()
                cursor_x = self.expansion_input.fontMetrics().boundingRect(input_text[:cursor_position]).width()

                # Adjust hint label position to shift 2 characters back
                char_width = self.expansion_input.fontMetrics().averageCharWidth() * 2
                adjusted_x = max(0, cursor_x + char_width)  # Ensure it doesn’t go below 0

                # Move and resize hint label based on the adjusted position
                self.hint_label.move(adjusted_x, 0)
                self.hint_label.resize(self.expansion_input.width() - adjusted_x - 4, self.expansion_input.height())
            else:
                self.hint_label.hide()
        else:
            self.hint_label.hide()

    def eventFilter(self, source, event):
        """Event filter to capture the 'Tab' key press."""
        if source == self.expansion_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == 0x01000001:  # Hex code for Qt.Key_Tab
                # Accept the suggestion if the Tab key is pressed
                if self.suggestion:
                    current_text = self.expansion_input.text()
                    new_text = current_text + self.suggestion
                    self.expansion_input.setText(new_text)
                    self.hint_label.hide()  # Hide the hint after accepting
                    return True
        return super().eventFilter(source, event)

    def is_connected(self):
        """Check if there is an internet connection."""
        try:
            requests.get("http://www.google.com", timeout=3)
            return True
        except (requests.ConnectionError, requests.Timeout):
            return False

    def closeEvent(self, event):
        """Handle the window close event"""
        self.cleanup_temporary_shortcuts()
        event.accept()
    
    def init_database(self):
        """Initialize the database for storing shortcuts. If the database file doesn't exist, create it, and if the table for shortcuts doesn't exist, create it. If the temporary column doesn't exist, add it."""
        
        db_path = os.path.join(os.path.expanduser('~'), 'text_expander.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shortcuts
            (shortcut TEXT PRIMARY KEY, 
             expansion TEXT)
        ''')
        
        # Check if temporary column exists, if not add it
        cursor.execute("PRAGMA table_info(shortcuts)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'temporary' not in columns:
            cursor.execute('ALTER TABLE shortcuts ADD COLUMN temporary BOOLEAN DEFAULT 0')
        
        self.conn.commit()

    def cleanup_temporary_shortcuts(self):
        """Clean up temporary shortcuts from previous session"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM shortcuts WHERE temporary = 1")
        self.conn.commit()

    def add_shortcut(self):
        """
        Adds a new shortcut to the text expander application.

        This method retrieves the shortcut and expansion text from the input fields, checks if they are valid, and inserts them into the database. It also sets up a keyboard hook for the added shortcut.

        Raises a warning message if the input fields are empty or if the shortcut already exists in the database. Clears the input fields and reloads the shortcuts after a successful addition.

        Exceptions:
            sqlite3.IntegrityError: If the shortcut already exists in the database.
            Exception: If any other error occurs during the database operation.
        """
        shortcut = self.shortcut_input.text().strip()  # shortcut
        expansion = self.expansion_input.text().strip()   # text to expand to
        temporary = self.temporary_checkbox.isChecked()  # if shortcut is temporary or not(temporary means erased from SQLite database when app closes)

        # ensure both fields are filled
        if not shortcut or not expansion:
            QMessageBox.warning(self, "Error", "Both fields are required!")
            return

        try:
            # insert into database
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO shortcuts (shortcut, expansion, temporary) 
                VALUES (?, ?, ?)""", (shortcut, expansion, temporary))
            self.conn.commit()
            
            # Clear inputs
            self.shortcut_input.clear()
            self.expansion_input.clear()
            self.temporary_checkbox.setChecked(False)
            
            # Reload shortcuts
            self.load_shortcuts()
            
            # Set up the keyboard hook
            keyboard.add_abbreviation(shortcut, expansion)
            
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "This shortcut already exists!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {str(e)}")

    def delete_shortcut(self, shortcut):
        """
        Deletes a shortcut from the text expander application.

        This method removes the keyboard hook for the given shortcut and deletes the shortcut from the database. If the keyboard hook removal fails, it still proceeds with the database deletion. A warning message is displayed if any error occurs during the process.

        Args:
            shortcut (str): The shortcut to be deleted.

        Exceptions:
            KeyError: If the shortcut does not exist in the keyboard hooks.
            Exception: If any other error occurs during the database operation.
        """
        try:
            # First remove the keyboard hook
            keyboard.remove_abbreviation(shortcut)
            
            # Then delete from database
            cursor = self.conn.cursor()
            query = "DELETE FROM shortcuts WHERE shortcut = ?"
            cursor.execute(query, (shortcut,))
            self.conn.commit()
            
            # Reload shortcuts
            self.load_shortcuts()
            
        except KeyError:
            # If keyboard hook removal fails, still proceed with database deletion
            cursor = self.conn.cursor()
            query = "DELETE FROM shortcuts WHERE shortcut = ?"
            cursor.execute(query, (shortcut,))
            self.conn.commit()
            self.load_shortcuts()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {str(e)}")

    def filter_shortcuts(self):
        """
        Filters the shortcuts based on the search text and displays the filtered shortcuts.
        
        This method is called whenever the search input field changes. It filters the shortcuts based on the search text, ignoring case, and displays the filtered shortcuts in the table widget.
        
        If the search text is empty, all shortcuts are displayed.
        """
        search_text = self.search_input.text().lower()
        
        # If search is empty, show all shortcuts
        if not search_text:
            self.display_shortcuts(self.all_shortcuts)
            return
        
        # Filter shortcuts based on search text
        filtered_shortcuts = [
            (shortcut, expansion, temporary) 
            for shortcut, expansion, temporary in self.all_shortcuts
            if search_text in shortcut.lower() or search_text in expansion.lower()
        ]
        
        self.display_shortcuts(filtered_shortcuts)
    
    def load_shortcuts(self):
        """
        Loads all shortcuts from the database and displays them.

        This method queries the database to retrieve all shortcuts, including their
        expansion text and temporary status, and stores them in the all_shortcuts
        attribute. It then displays these shortcuts in the table widget.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT shortcut, expansion, temporary FROM shortcuts")
        self.all_shortcuts = cursor.fetchall()
        self.display_shortcuts(self.all_shortcuts)

    def setup_shortcuts_in_listener(self):
        """Sets up keyboard abbreviations for each shortcut from the database."""
        for shortcut, expansion, _ in self.all_shortcuts:  # Ignore the 'temporary' field
            keyboard.add_abbreviation(shortcut, expansion)
    
    def display_shortcuts(self, shortcuts):
        """
        Displays the given shortcuts in the table widget, with columns for the
        shortcut, expansion, temporary status, and a delete button.

        Args:
            shortcuts (list[tuple[str, str, bool]]): The list of shortcuts to
                display, where each tuple contains the shortcut, expansion text,
                and whether the shortcut is temporary.
        """
        self.table.setRowCount(len(shortcuts))
        
        for i, (shortcut, expansion, temporary) in enumerate(shortcuts):
            self.table.setItem(i, 0, QTableWidgetItem(shortcut))
            self.table.setItem(i, 1, QTableWidgetItem(expansion))
            
            # Add temporary status
            temp_item = QTableWidgetItem("Yes" if temporary else "No")
            temp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, temp_item)
            
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda checked, s=shortcut: self.delete_shortcut(s))
            self.table.setCellWidget(i, 3, delete_button)

    def start_keyboard_listener(self):
        # Load existing shortcuts into keyboard listener
        """
        Starts the keyboard listener and loads existing shortcuts into it.
        This method starts a keyboard listener that listens for the shortcuts loaded from the database and expands them when entered. It queries the database to retrieve all shortcuts, along with their expansion text, and loads them into the keyboard listener using the add_abbreviation method. It then starts the listener using the wait method, which blocks until the listener is stopped.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT shortcut, expansion FROM shortcuts")
        shortcuts = cursor.fetchall()
        
        for shortcut, expansion in shortcuts:
            keyboard.add_abbreviation(repr(shortcut), expansion)
        
        # Start the keyboard listener
        keyboard.wait()

def main():
    """
    Entry point of the application. Creates a QApplication, instantiates a TextExpanderApp instance, shows it, and starts the application event loop with exec().

    This function is the entry point of the application and is called when the script is run directly (i.e. not imported as a module).
    """
    app = QApplication(sys.argv)
    window = TextExpanderApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()