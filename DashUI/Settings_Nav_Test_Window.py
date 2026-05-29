import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import Settings_Handler

# ==============================================================================
# SETTINGS OVERLAY WIDGET
# ==============================================================================

class SettingsOverlayWidget(QWidget):
    def __init__(self, parent, handler: Settings_Handler.SettingsHandler, box_color="#111116", text_color="#000000", highlight_color="#FFCC00", text_highlight="#000000"):
        super().__init__(parent)
        self.handler = handler
        
        # 800x480 screen with 20px bounds buffer = 760x440 dimensions
        self.setGeometry(20, 20, 760, 440)
        self.setStyleSheet(f"background-color: {box_color}")
        
        # Define the font globally here so it's easily modifiable
        self.item_font = QFont("Ubuntu", 36, QFont.Bold)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.show_timer = QTimer()
        self.show_timer.setSingleShot(True)
        self.show_timer.timeout.connect(self.hide)
        
        # Header setup
        self.header_label = QLabel("SETTINGS", self)
        self.header_label.setFont(QFont("Ubuntu", 18, QFont.Bold))
        self.header_label.setStyleSheet("color: #CCCCCC; padding-bottom: 8px; letter-spacing: 2px;")
        layout.addWidget(self.header_label)

        # 2-Column Table Widget
        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(2)
        self.table_widget.setFocusPolicy(Qt.NoFocus)
        
        # Apply the base font to the widget itself as a fallback
        self.table_widget.setFont(self.item_font)
        
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setVisible(False)
        self.table_widget.setShowGrid(False)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        # Cleaned up CSS (font-size and font-weight removed from here since they are handled via Python)
        self.table_widget.setStyleSheet(f"""
            QTableWidget {{
                background-color: {box_color};
                border: 3px solid #999999;
                padding: 2px;
            }}
            QTableWidget::item {{
                padding-left: 20px;
                padding-right: 20px;
                color: {text_color};
            }}
            QTableWidget::item:selected {{
                background-color: {highlight_color};
                color: {text_highlight};
            }}
        """)
        layout.addWidget(self.table_widget)
        self.update_view()
        self.hide()

    def format_setting_value(self, name: str, value: int) -> str:
        if name == "Presets":
            return self.handler.presets[value].name.upper()
        if name in ["TC"]:
            if value == 11:
                return "OFF"
            elif value >= 8:
                return f"(LOW) {value}"
            elif value >= 4:
                return f"(MED) {value}"
            else:
                return f"(HI) {value}"
        if name in ["FuelMix"]:
            if value > 0:
                return f"(RICH) {value}"
            elif value < 0:
                return f"(LEAN) {value}"
        if name in ["AeroMode"]:
            strs = ["OFF", "AUTO", "LOW DRAG", "TRIM"]
            return strs[value]
        if name in ["AeroSens"]:
            strs = ["BALANCED", "AGGRO", "ATTACK", "LAZY", "SAFE"]
            return strs[value]
        if name in ["AeroBal"]:
            if value >= 6:
                return "MAX F"
            elif value > 0:
                return f"(F) {value}"
            elif value <= -6:
                return "MAX R"
            elif value < 0:
                return f"(R) {value}"
        return str(value)

    def update_view(self):
        self.table_widget.clearContents()
        
        if not self.handler.in_group_menu:
            self.header_label.setText("SETTING GROUPS")
            self.table_widget.setRowCount(len(self.handler.groups))
            
            for row, group in enumerate(self.handler.groups):
                self.table_widget.setRowHeight(row, 89)
                
                name_item = QTableWidgetItem(group.name.upper())
                name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                name_item.setFont(self.item_font)  # Direct font injection
                
                dir_item = QTableWidgetItem("> ")
                dir_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                dir_item.setFont(self.item_font)  # Direct font injection
                
                self.table_widget.setItem(row, 0, name_item)
                self.table_widget.setItem(row, 1, dir_item)
                
            self.table_widget.setCurrentCell(self.handler.selected_group_idx, 0)
        else:
            active_group = self.handler.groups[self.handler.selected_group_idx]
            self.header_label.setText(f"GROUP  >  {active_group.name.upper()}")
            self.table_widget.setRowCount(len(active_group.settings))
            
            for row, setting in enumerate(active_group.settings):
                self.table_widget.setRowHeight(row, 85)
                
                name = setting.rule[0]
                display_val = self.format_setting_value(name, setting.value)
                
                name_item = QTableWidgetItem(name.upper())
                name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                name_item.setFont(self.item_font)  # Direct font injection
                
                val_item = QTableWidgetItem(display_val)
                val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                val_item.setFont(self.item_font)  # Direct font injection
                
                self.table_widget.setItem(row, 0, name_item)
                self.table_widget.setItem(row, 1, val_item)
                
            self.table_widget.setCurrentCell(self.handler.selected_setting_idx, 0)

    def show_for(self, duration=1500):
        self.show()
        self.show_timer.start(duration)




# ==============================================================================
# INTERACTIVE SIMULATOR WINDOW
# ==============================================================================

class DashSimulatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FSAE Dash Configuration Simulator")
        self.setFixedSize(800, 480)
        
        # Base window styling (representing background layout screens)
        self.setStyleSheet("background-color: #0B0C10;")
        
        # Background canvas layers layout placeholder
        bg_label = QLabel("MAIN PAGE DISPLAY LAYER\n(Telemetry, Lap times, RPM lights hidden beneath menu popup)", self)
        bg_label.setGeometry(0, 0, 800, 480)
        bg_label.setAlignment(Qt.AlignCenter)
        bg_label.setStyleSheet("color: #1F2833; font-size: 16px; font-weight: bold;")

        # Diagnostic telemetry print bar on screen bottom
        self.status_bar = QLabel("System Status: Normal", self)
        self.status_bar.setGeometry(20, 445, 760, 30)
        self.status_bar.setStyleSheet("color: #45A29E; font-family: Consolas; font-size: 12px;")

        # Instantiate settings suite controller engine
        self.handler = Settings_Handler.SettingsHandler()
        
        # Initialize custom configurable menu layout component
        # Modify hexadecimal values here to change colors dynamically
        self.settings_menu = SettingsOverlayWidget(
            parent=self, 
            handler=self.handler,
            box_color="#151515",
            text_color="#DDDDDD",
            highlight_color="#0033FF",   
            text_highlight="#DDDDDD"
        )

    def keyPressEvent(self, event):
        self.settings_menu.show_for(1500)
        """Simulates physical steering wheel buttons using hardware keys."""
        action_logged = ""

        if event.key() == Qt.Key_Up:
            action_logged = self.handler.scroll_menu(up=False)
        elif event.key() == Qt.Key_Down:
            action_logged = self.handler.scroll_menu(up=True)
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            action_logged = self.handler.toggle_menu_depth()
        elif event.key() == Qt.Key_Right:
            adjust_res = self.handler.adjust_setting(up=True)
            if adjust_res: action_logged = f"Increased {adjust_res[0]} to {adjust_res[1]}"
        elif event.key() == Qt.Key_Left:
            adjust_res = self.handler.adjust_setting(up=False)
            if adjust_res: action_logged = f"Decreased {adjust_res[0]} to {adjust_res[1]}"
        elif event.key() == Qt.Key_Space:
            action_logged = self.handler.commit_preset()

        # Refresh graphics loop mapping states
        self.settings_menu.update_view()
        
        # Feed changes to the live simulator footer
        if action_logged:
            self.status_bar.setText(f"Last Event: {action_logged}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    simulator = DashSimulatorWindow()
    simulator.show()
    sys.exit(app.exec_())