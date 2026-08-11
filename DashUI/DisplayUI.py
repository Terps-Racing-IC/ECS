'''
!!! Need to run !!!

sudo apt update
sudo apt install libgl1

# pip3 install PyQt5
# pip3 install pyqtgraph
# pip3 install python-can
# sudo pip3 install --break-system-packages adafruit-circuitpython-neopixel rpi_ws281x

For first time setup on the system

TODO:
'''

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt5.QtCore import QTimer, Qt, QRect, QObject, QThread, pyqtSignal
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QFont, QPainter, QColor, QCursor
import sys
import random
import traceback
from CAN_Handler import CanCommon, CanWrapper
from LED_Handler import LedController, LedBehavior
from Settings_Handler import SettingsHandler
from gpiozero import Device, RotaryEncoder, DigitalInputDevice
from gpiozero.pins.mock import MockFactory

#Device.pin_factory = MockFactory() # This line can be used to run the program without hardware connected. 
# Must be commented out in order to work with hardware connected

'''
#####################################

Funny snake code

#####################################
'''
class SnakeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

        self.setGeometry(20,0, 760, 456)

        # Game grid will be 40x24
        self.snake = [(35,12), (36,12), (37,12)]
        self.direction = [-1, 0] # First number = left/right direction, second number = up/down direction
        self.food = (15, 12)
        self.score = 0
        self.inc = 0
        
        
        self.score_label = QLabel("0", self)
        self.score_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.score_label.setFont(QFont("Ubuntu", 20, QFont.DemiBold))
        self.score_label.setStyleSheet("""
            color: rgb(220, 220, 220);
            background: transparent;
        """)
        self.score_label.setFixedWidth(100)
        self.score_label.move(680, 10)
        

    def reset_game(self):
        self.snake = [(35,12), (36,12), (37,12)]
        self.direction = [-1, 0] # First number = left/right direction, second number = up/down direction
        self.food = (15, 12)
        self.score = 0
        self.score_label.setText("0")
    
    def update_game(self):
        if self.inc == 2:
            self.inc = 0
            head_x, head_y = self.snake[0]
            newhead = ((head_x + self.direction[0]) % 40, (head_y + self.direction[1]) % 24)
            if newhead in self.snake:
                self.reset_game()
            else:
                self.snake.insert(0, ((head_x + self.direction[0]) % 40, (head_y + self.direction[1]) % 24))
                if self.snake[0] == self.food:
                    self.score = self.score + 1
                    while True:
                        fx, fy = (random.randint(0, 39), random.randint(0,23))
                        if (fx, fy) not in self.snake:
                            self.food = (fx, fy)
                            break
                else:
                    self.snake.pop()

            self.score_label.setText(f"{self.score}")
            self.update()
        else:
            self.inc = self.inc + 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30,30,30))

        painter.setBrush(QColor(200, 220, 200))
        for x,y in self.snake:
            painter.drawRect(x*19 + 20, y*19, 19, 19)
        
        painter.setBrush(QColor(220, 20, 20))
        fx,fy = self.food
        painter.drawRect(fx*19 + 20, fy*19, 19, 19)

    def keyPressEvent(self, event):
        match event.key():
            case Qt.Key_Up:
                if self.direction != [0, 1]:
                    self.direction = [0, -1]
            case Qt.Key_Down:
                if self.direction != [0, -1]:
                    self.direction = [0, 1]
            case Qt.Key_Right:
                if self.direction != [-1, 0]:
                    self.direction = [1, 0]
            case _:
                if self.direction != [1, 0]:
                    self.direction = [-1, 0]


''' 
#######################################

        SETTINGS HANDLER CODE

#######################################
'''

class SettingsOverlayWidget(QWidget):
    def __init__(self, parent, handler: SettingsHandler, box_color="#111116", text_color="#000000", highlight_color="#FFCC00", text_highlight="#000000"):
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
        self.table_widget.clearSelection()
        
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

'''
####################################################

                    DISPLAY CODE

####################################################
'''


class Dashboard(QWidget):
    def __init__(self):
        print("Starting dashboard init...")
        super().__init__()
        # Colors and sizes to make adjusting stuff easier
        self.white_color = "rgb(255, 255, 255)"
        self.black_color = "rgb(0, 0, 0)"
        self.info_color = "rgb(20, 100, 255)"
        self.warn_color = "rgb(255, 20, 20)"
        self.text_font_size = 20
        self.subtitle_size = 10
        # Set up window
        self.setWindowTitle("FSAE Dashboard")
        self.setGeometry(0, 0, 800, 480)  # x, y, width, height

        self.setCursor(QCursor(Qt.BlankCursor)) # Hides the mouse cursor while the program is shown; the driver doesn't need to see it and it's annoying.
        # Set up page layout that can be switched between
        self.pages = QStackedWidget(self)
        self.pages.setGeometry(0, 0, 800, 480)  # x, y, width, height
        self.pages.setStyleSheet(f"background-color: {self.black_color}")  # Black background
        self.pages.currentChanged.connect(self.on_page_switched)

        self.snake_letters_typed = 0
        
        # 
        # MAIN PAGE
        #

        self.page_main = QWidget()
        self.init_page_main(self.page_main)
        self.pages.addWidget(self.page_main)

        #
        # RAW PAGE
        #

        self.page_raw = QWidget()
        self.init_page_raw(self.page_raw)
        self.pages.addWidget(self.page_raw)

        #
        # OTHER PAGES HERE
        #

        #
        # SNAKE PAGE
        #
        self.page_snake = SnakeWidget(parent=self)
        self.pages.addWidget(self.page_snake)

        self.pages.setCurrentIndex(0)


        # UPDATE STUFF
        # Start the CAN bus and move it to thread
        print("Starting CAN thread...") # CAN gets its own thread so it doesn't block the GUI
        self.can_thread = QThread()
        self.can_common = CanCommon() # CREATE A CANCOMMON OBJECT THAT STORES ALL CAN INFO
        self.can_common.moveToThread(self.can_thread)

        self.can_thread.started.connect(self.can_common.start)
        self.can_thread.start()

        self.can_common.snapshot_ready.connect(self.can_ready)

        self.canObject = CanWrapper({"TC": 11})

        # Start the LED controller
        print("Starting LED Controller...")
        self.ledController = LedController(16) # For 16 LEDs

        # Create GPIO for the encoders:
        print("Setting up rotary encoders...")
        try:
            self.encoder_adjust = RotaryEncoder(a=17, b=27, bounce_time=0.005)
            self.encoder_adjust.when_rotated_clockwise = self.adjust_setting_cw
            self.encoder_adjust.when_rotated_counter_clockwise = self.adjust_setting_ccw

            self.encoder_select = [
                DigitalInputDevice(19, pull_up=True),
                DigitalInputDevice(5, pull_up=True),
                DigitalInputDevice(13, pull_up=True),
                DigitalInputDevice(6, pull_up=True)
            ]

            self.encoder_button_confirm = DigitalInputDevice(16, pull_up=True) # Button to confirm preset changes
            self.button_timer = QTimer()
            self.button_timer.setSingleShot(True)

        except Exception as e:
            self.encoder_adjust = None
            self.encoder_select = None
            print(f"Error setting up input device: {e}")
        self.settings = SettingsHandler()
        self.prev_abs_enc_position = 0

        self.settings_menu = SettingsOverlayWidget(
            parent=self, 
            handler=self.settings,
            box_color="#151515",
            text_color="#DDDDDD",
            highlight_color="#0033FF",   
            text_highlight="#DDDDDD"
        )

        self.settings.output_to_ECU()
        self.settings.output_gear_to_ECU(0,0)
        self.pending_setting_message = None
        self.redraw_setting_menu = False

        self.ui_timer = QTimer()
        # Each time the timers complete, we poll the CAN bus, 
        # update the selected display page, update the LEDs, and update the global ambient alert system
        self.ui_timer.timeout.connect(self.update_LEDs)
        self.ui_timer.timeout.connect(self.update_display)
        self.ui_timer.timeout.connect(self.update_ambient_alert)
        self.ui_timer.timeout.connect(self.select_setting)
        self.ui_timer.timeout.connect(self.handle_pending_alert)
        self.ui_timer.start(40) # This line determines update period in ms. It easily runs at 25Hz and can probably go faster

        # ALERTS   ALERTS   ALERTS   ALERTS   ALERTS   ALERTS #
        # Warning/Ambient alert: colored border with critical info
        self.warning_alert_background = WarnAlertWidget(self)
        self.warning_alert_text = QLabel("Coolant Overtemp", self)
        self.warning_alert_text.setFont(QFont('Ubuntu', 18, QFont.DemiBold))
        self.warning_alert_text.setStyleSheet(f"""
                                            color: {self.black_color};
                                            background-color: rgba(0, 0, 0, 0);
                                            padding: 0px 10px;
                                           """)
        self.warning_alert_text.move(0, 445)
        #self.warning_alert_background.setColor(QColor(189, 172, 23))
        self.warning_alert_background.hide()
        self.warning_alert_text.hide()
        self.warning_alert_text.resize(760, 35)
        self.warnings = [0, 0, 0, 0] # This array will simply hold whether each alert is active
        # 0: coolant, 1: oil pressure, 2: Fuel, 3: Battery
        self.warning_alert_text.buffer = set()
        self.warning_alert_text.shown = False

        # Info alert: full screen rectangle
        self.info_alert_background = QWidget(self)
        self.info_alert_background.setStyleSheet(f"""
                                                 background-color: {self.info_color};
                                                 """) # default color
        self.info_alert_background.setGeometry(25, 25, 750, 430)  # x, y, width, height
        self.info_alert_background.hide()

        self.info_alert_text = QLabel("NO ALERT", self.info_alert_background)
        self.info_alert_text.setAlignment(Qt.AlignLeft)
        self.info_alert_text.setFont(QFont('Ubuntu', 80, QFont.DemiBold))
        self.info_alert_text.setStyleSheet(f"""
                                      color: {self.black_color};
                                      background-color: rgba(0, 0, 0, 0);
                                      padding: 15px 15px;
                                      """)
        self.info_alert_text.setGeometry(25, 25, 750, 430)
        self.info_alert_text.hide()

        self.alert_timer = QTimer()
        self.alert_timer.setSingleShot(True)
        self.alert_timer.timeout.connect(self.info_alert_background.hide)
        self.alert_timer.timeout.connect(self.info_alert_text.hide)
        self.bb_timer = QTimer()
        self.bb_timer.setSingleShot(True)
        self.bb_timer.timeout.connect(self.bb_advise)

        print("Finished main page setup")

    def closeEvent(self, event):
        # Stop CAN polling
        self.can_common.stop()
    
        # Quit thread
        self.can_thread.quit()
        self.can_thread.wait()  # blocks until thread exits

        # Continue with normal close
        event.accept()
    
    def can_ready(self, value):
        self.canObject = value

    ''' Encoder stuff '''

    # This function pair handles the settings adjustment rotary encoder.
    def adjust_setting_cw(self):
        adjusted = self.settings.adjust_setting(True)
        if adjusted is not None:
            name, val = adjusted
            self.can_common.update_values_request.emit({name: val})
            self.redraw_setting_menu = True
            #self.alert_caller(name,val)
    def adjust_setting_ccw(self):
        adjusted = self.settings.adjust_setting(False)
        if adjusted is not None:
            name, val = adjusted
            self.can_common.update_values_request.emit({name: val})
            self.redraw_setting_menu = True
            #self.alert_caller(name,val)
    def commit_preset(self):
        commit = self.settings.commit_preset()
        if commit is not None:
            selected, settings = commit
            self.pending_setting_message = ("Selected", selected, "rgb(255,255,255)", 2000)
            self.can_common.update_values_request.emit(settings)
            if "wet" in selected.lower():
                self.bb_timer.start(3000)

    def bb_advise(self):
        self.pending_setting_message = ("ADVISE", "Brake -30", "rgb(255,151,54)", 10000)

    ''' DEPRICATED
    def alert_caller(self,name="",val=0):
        match name:
            case "FuelMix": 
                if val > 0:
                    val = f"+{val} (RICH)"
                elif val < 0:
                    val = f"{val} (LEAN)"
                self.pending_setting_message = ("Fuel Mix", f"{val}", "rgb(255,100,100)",1000)
            case "TC":
                if val == 11:
                    val = "OFF"
                elif val <= 2:
                    val = f"{val} (HIGH)"
                elif val <= 7:
                    val = f"{val} (MED)"
                else:
                    val = f"{val} (LOW)"
                self.pending_setting_message = ("TC", f"{val}", "rgb(0,224,194)", 1000)
            case "AeroSens": 
                text = ["Lazy","Safe","Balanced","Aggressive","Attack"]
                self.pending_setting_message = ("Aero Sens", f"{text[val+2]}", "rgb(52,255,52)", 1000)
            case "AeroMode": 
                if val == 3:
                    val = "TRIM"
                elif val == 2:
                    val = "LOW DRAG"
                elif val == 1:
                    val = "AUTO"
                else:
                    val = "OFF"
                self.pending_setting_message = ("Aero Mode", f"{val}", "rgb(52,255,52)", 1000)
            case "AeroBal": 
                if val < -5:
                    val = f"{val} (MAX R)"
                elif val < 0:
                    val = f"{val} (R)"
                elif val > 5:
                    val = f"{val} (MAX F)"
                elif val > 0:
                    val = f"{val} (F)"
                self.pending_setting_message = ("Aero Bal", f"{val}", "rgb(52,150,255)", 1000)
            case "AeroShift": self.pending_setting_message = ("Aero Shift", f"{val}", "rgb(52,150,255)", 1000)
            #case "FArb": self.pending_setting_message = ("Front Arb", f"{val}", "rgb(235,222,52)", 1000)
            case "Brightness": self.pending_setting_message = ("Brightness", f"{val}%", "rgb(255,255,255)", 1000)
            case "Presets": self.pending_setting_message = ("Preset", f"{self.settings.presets[val].name}", "rgb(255,255,255)", 1000)
            case _: return
    '''

    # This function handles the absolute encoder's position.
    def select_setting(self):
        self.settings.output_gear_to_ECU(self.canObject.get("Gear"),self.canObject.get("Neutral"))
        self.settings.output_to_ECU()

        if self.encoder_select is None or self.encoder_button_confirm is None:
            return

        g3 = self.encoder_select[3].value
        g2 = self.encoder_select[2].value
        g1 = self.encoder_select[1].value
        g0 = self.encoder_select[0].value
        gray = (g3 << 3) | (g2 << 2) | (g1 << 1) | g0
        bin = [0, 1, 3, 2, 7, 6, 4, 5, 15, 14, 12, 13, 8, 9, 11, 10]  # Gray code will be used as an index
        button = self.encoder_button_confirm.value

        if bin[gray] == 0 and self.prev_abs_enc_position == 15:
            self.settings.scroll_menu(True)
            self.redraw_setting_menu = True
        elif bin[gray] == 15 and self.prev_abs_enc_position == 0:
            self.settings.scroll_menu(False)
            self.redraw_setting_menu = True
        elif bin[gray] > self.prev_abs_enc_position: # Only update if we actually changed the setting
            self.settings.scroll_menu(True)
            self.redraw_setting_menu = True
        elif bin[gray] < self.prev_abs_enc_position:
            self.settings.scroll_menu(False)
            self.redraw_setting_menu = True
        elif button == 1 and not self.button_timer.isActive(): # If misused this may cause a loop of messages, but it should be fine
            group = self.settings.groups[self.settings.selected_group_idx]
            if self.settings.in_group_menu and group.name == "System" and group.settings[self.settings.selected_setting_idx].rule[0] == "Presets":
                self.commit_preset()
            self.settings.toggle_menu_depth()
            self.redraw_setting_menu = True
            self.button_timer.start(500)
        if bin[gray] != self.prev_abs_enc_position:
            self.redraw_setting_menu = True
            self.prev_abs_enc_position = bin[gray]

        if self.redraw_setting_menu:
            self.settings_menu.show_for(2000)
            self.settings_menu.update_view()
            self.redraw_setting_menu = False
    ''' Page setups '''

    def init_page_main(self, page):
        # Create labels like this
        # RPM Text Display
        self.rpm_label = QLabel("   13800  ", page)
        self.rpm_label.setAlignment(Qt.AlignCenter)
        self.rpm_label.setFont(QFont('Ubuntu', self.text_font_size*2, QFont.DemiBold))
        self.rpm_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 8px; 
                                     """)
        self.rpm_label.move(254, 57)  # x, y
        # RPM Subtitle
        self.rpm_subtitle = QLabel("RPM", page)
        self.rpm_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.rpm_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: {self.black_color};
                                        padding: 0px 3px;
                                        """)
        self.rpm_subtitle.move(378, 122)

        
        # RPM Bar
        self.max_rpm = 13800
        self.rpm_bar_bg = QWidget(page)
        self.rpm_bar_bg.setStyleSheet("background-color: rgb(30, 30, 30);")
        self.rpm_bar_bg.setGeometry(0, 0, 800, 42)  # x, y, width, height

        self.rpm_bar_fill = QWidget(self.rpm_bar_bg)
        self.rpm_bar_fill.setGeometry(0, 0, 0, 42)  # Will update width dynamically
        self.rpm_bar_fill.setStyleSheet("background-color: rgb(255, 255, 0);")
        #self.rpm_bar_color = None


        # Throttle and Brake bars
        # Throttle
        self.tps_bar_bg = QWidget(page)
        self.tps_bar_bg.setStyleSheet("background-color: rgb(30, 30, 30)")
        self.tps_bar_bg.setGeometry(510, 144, 10, 230)
        self.tps_fill = QWidget(self.tps_bar_bg)
        self.tps_fill.setStyleSheet("background-color: rgb(20, 200, 20)")
        self.tps_fill.setGeometry(0,250,30,0)
        # Brake
        self.brake_bar_bg = QWidget(page)
        self.brake_bar_bg.setStyleSheet("background-color: rgb(30, 30, 30)")
        self.brake_bar_bg.setGeometry(284, 144, 10, 230)
        self.brake_fill = QWidget(self.brake_bar_bg)
        self.brake_fill.setStyleSheet("background-color: rgb(200, 20, 20)")
        self.brake_fill.setGeometry(0,250,30,0)



        # Speed Label
        self.speed_label = QLabel("RPM: 13800", page) # Placeholder text to be the correct size
        self.speed_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.speed_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.speed_label.setAlignment(Qt.AlignCenter)
        self.speed_label.move(298, 327)  # x, y

        self.speed_subtitle = QLabel("mph", page)
        self.speed_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.speed_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: {self.black_color};
                                        padding: 0px 3px;
                                        """)
        self.speed_subtitle.move(378, 363)


        # DRS Indicator
        self.drs = QLabel("DRS", page)
        self.drs.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.drs.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.drs.setAlignment(Qt.AlignCenter)
        #self.drs.move(722, 42) # Old position on side of screen
        self.drs.move(691, 57)
        self.drs.state = 0
        # Active setting indicator:
        self.active_setting = QLabel("Low-Drag", page)
        self.active_setting.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.active_setting.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.active_setting.setAlignment(Qt.AlignCenter)
        #self.active_setting.move(653, 86)
        self.active_setting.move(608, 103)
        # AA Subtitle
        self.active_subtitle = QLabel("AA", page)
        self.active_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.active_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: "rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        #self.active_subtitle.move(667, 139)
        self.active_subtitle.move(752, 131)


        # Active Sensitivity indication
        self.active_sens_label = QLabel("Low-Drag", page)
        self.active_sens_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.active_sens_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.active_sens_label.setAlignment(Qt.AlignCenter)
        self.active_sens_label.move(608, 149)
        # Brake bias subtutle
        self.active_sens_subtitle = QLabel("Sens", page)
        self.active_sens_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.active_sens_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: "rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        self.active_sens_subtitle.move(740, 177)

        # Aero balance indicator
        self.active_bal_label = QLabel("Low-Drag", page)
        self.active_bal_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.active_bal_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.active_bal_label.setAlignment(Qt.AlignCenter)
        self.active_bal_label.move(608, 195)
        # Aero balance subtutle
        self.active_bal_subtitle = QLabel("Aero Bal", page)
        self.active_bal_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.active_bal_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: "rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        self.active_bal_subtitle.move(715, 223)

        # Aero migration lable
        self.aero_shift_label = QLabel("Low-Drag", page)
        self.aero_shift_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.aero_shift_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.aero_shift_label.setAlignment(Qt.AlignCenter)
        self.aero_shift_label.move(608, 241)
        # Aero migration lable
        self.aero_shift_subtitle = QLabel("Aero Shft", page)
        self.aero_shift_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.aero_shift_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: "rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        self.aero_shift_subtitle.move(707, 269)


        # LC Indicator
        #                "DRS"
        self.lc = QLabel("  LC  ", page)
        self.lc.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.lc.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.lc.setAlignment(Qt.AlignCenter)
        self.lc.move(20, 57)
        self.lc.state = 0


        # TC Indicator
        self.tc = QLabel("Low-Drag", page)
        self.tc.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.tc.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.tc.setAlignment(Qt.AlignCenter)
        self.tc.color = self.white_color
        self.tc.move(20, 103)

        # TC Subtitle
        self.tc_subtitle = QLabel("TC", page)
        self.tc_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.tc_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        # self.tc_subtitle.move(80, 139)
        self.tc_subtitle.move(20, 131)

        # Fuel Mixture
        self.fuel_mixture_label = QLabel("Low-Drag", page)
        self.fuel_mixture_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.fuel_mixture_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.fuel_mixture_label.setAlignment(Qt.AlignCenter)
        self.fuel_mixture_label.color = self.white_color
        self.fuel_mixture_label.move(20, 149)

        # Fuel Mixture Subitle (goes above due to layout issues)
        self.fuel_mix_subtitle = QLabel("Fuel Mix", page)
        self.fuel_mix_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.fuel_mix_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        # self.fuel_mix_subtitle.move(60, 189)
        self.fuel_mix_subtitle.move(20, 177)

        # LED brightness label
        self.led_label = QLabel("Low-Drag", page)
        self.led_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.led_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.led_label.setAlignment(Qt.AlignCenter)
        self.led_label.color = self.white_color
        self.led_label.move(20, 195)

        # LED Subtitle
        self.led_subtitle = QLabel("LED b", page)
        self.led_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.led_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        # self.led_subtitle.move(60, 189)
        self.led_subtitle.move(20, 223)

        # Brake Bias Setting
        self.bbal_label = QLabel("Low-Drag", page)
        self.bbal_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.bbal_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.bbal_label.setAlignment(Qt.AlignCenter)
        self.bbal_label.color = self.white_color
        self.bbal_label.move(20, 241)

        # Fuel Mixture Subitle (goes above due to layout issues)
        self.bbal_subtitle = QLabel("B Bias", page)
        self.bbal_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.bbal_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: rgba(0, 0, 0, 0);
                                        padding: 0px 3px;
                                        """)
        # self.led_subtitle.move(60, 189)
        self.bbal_subtitle.move(20, 269)


        # Battery Indicator
        self.battery_label = QLabel("14.9 V", page)
        self.battery_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.battery_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        self.battery_label.resize(190,56)
        self.battery_label.setAlignment(Qt.AlignCenter)
        self.battery_label.move(20, 389)
        # Battery Subtitle
        self.battery_subtitle = QLabel("Battery", page)
        self.battery_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.battery_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: {self.black_color};
                                        padding: 0px 3px;
                                        """)
        self.battery_subtitle.move(85, 382)


        # Coolant temperature
        self.coolant_label = QLabel("14.9 V", page)
        self.coolant_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.coolant_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        self.coolant_label.resize(190,56)
        self.coolant_label.setAlignment(Qt.AlignCenter)
        self.coolant_label.move(210, 389)
        # Coolant subtitle
        self.coolant_subtitle = QLabel("Water Temp", page)
        self.coolant_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.coolant_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: {self.black_color};
                                        padding: 0px 3px;
                                        """)
        self.coolant_subtitle.move(258, 382)


        # Oil pressure
        self.oil_label = QLabel("14.9 V", page)
        self.oil_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.oil_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        self.oil_label.resize(190,56)
        self.oil_label.setAlignment(Qt.AlignCenter)
        self.oil_label.move(400, 389)
        # Oil subtitle
        self.oil_subtitle = QLabel("Oil Press", page)
        self.oil_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.oil_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: {self.black_color};
                                        padding: 0px 3px;
                                        """)
        self.oil_subtitle.move(455, 382)


        # Fuel :)
        self.fuel_label = QLabel("14.9 V", page)
        self.fuel_label.setFont(QFont('Ubuntu', self.text_font_size, QFont.DemiBold))
        self.fuel_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        self.fuel_label.resize(190,56)
        self.fuel_label.setAlignment(Qt.AlignCenter)
        self.fuel_label.move(590, 389)
        # Fuel subtitle
        self.fuel_subtitle = QLabel("Fuel", page)
        self.fuel_subtitle.setFont(QFont('Ubuntu', self.subtitle_size, QFont.DemiBold))
        self.fuel_subtitle.setStyleSheet(f"""
                                        color: {self.white_color};
                                        background-color: {self.black_color};
                                        padding: 0px 3px;
                                        """)
        self.fuel_subtitle.move(663, 382)


        # Gear indicator
        self.gear_label = QLabel("N", page)
        self.gear_label.setFont(QFont('Ubuntu', 90, QFont.Bold))
        self.gear_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     border: 2px solid {self.white_color};
                                     padding: 20px 40px;
                                     """)
        self.gear_label.setAlignment(Qt.AlignCenter)
        self.gear_label.move(309, 144)
        self.gear_color = None

        # Mini label for TPS so the driver can set up their launch
        self.tps_small = QLabel("TPS: 100.0", page)
        self.tps_small.setFont(QFont('Ubuntu', self.subtitle_size+5, QFont.Bold))
        self.tps_small.setStyleSheet(f"""
                                     color: {self.white_color};
                                     """)
        self.tps_small.setAlignment(Qt.AlignLeft)
        self.tps_small.move(525, 354)

        self.lambda_small = QLabel("L02: 1.27", page)
        self.lambda_small.setFont(QFont('Ubuntu', self.subtitle_size+5, QFont.Bold))
        self.lambda_small.setStyleSheet(f"""
                                     color: {self.white_color};
                                     """)
        self.lambda_small.setAlignment(Qt.AlignLeft)
        self.lambda_small.move(175, 354)

    def init_page_raw(self, page):
        white_style = f"color: {self.white_color};"
        default_font = QFont('Ubuntu', self.text_font_size, QFont.DemiBold)
        large_font = QFont('Ubuntu', self.text_font_size * 2, QFont.DemiBold)

        # Define widgets and their properties
        widgets = {
            "gear_raw":      ("Gear: 6", (25, 20), Qt.AlignLeft, large_font),
            "speed_raw":     ("Speed: 200", (25, 80), Qt.AlignLeft, default_font),
            "TPS_raw":       ("TPS: 100", (25, 110), Qt.AlignLeft, default_font),
            "RPM_raw":       ("RPM: 13800", (25, 140), Qt.AlignLeft, default_font),
            "lambda_raw":    ("LO2: 1.27", (25, 170), Qt.AlignLeft, default_font),
            "oil_raw":       ("EOP: 10000", (25, 200), Qt.AlignLeft, default_font),
            "coolant_raw":   ("Coolant: 255", (25, 230), Qt.AlignLeft, default_font),
            "ws_raw":        ("Wheel Speeds", (25, 265), Qt.AlignCenter, default_font),
            "WSFL_raw":      ("200", (25, 300), Qt.AlignCenter, large_font),
            "WSFR_raw":      ("200", (125, 300), Qt.AlignCenter, large_font),
            "WSRL_raw":      ("200", (25, 380), Qt.AlignCenter, large_font),
            "WSRR_raw":      ("200", (125, 380), Qt.AlignCenter, large_font),
            "tc_raw":        ("TC: OFF", (290, 80), Qt.AlignLeft, default_font),
            "mix_raw":       ("Fuel Mix: -10", (290, 110), Qt.AlignLeft, default_font),
            "AA_set_raw":    ("Active Aero: AUTO", (290, 140), Qt.AlignLeft, default_font),
            "fuel_raw":      ("Fuel: 100", (290, 200), Qt.AlignLeft, default_font),
            "battery_raw":   ("Battery: 13.9", (290, 230), Qt.AlignLeft, default_font),
            "fbrake_raw":    ("Front Brake: 450", (290, 270), Qt.AlignLeft, default_font),
            "rbrake_raw":    ("Rear Brake: 450", (290, 300), Qt.AlignLeft, default_font),
            "steer_angle_raw":("Steering Angle: -780", (290, 350), Qt.AlignLeft, default_font),
            "DRS_raw":       ("DRS: OFF", (600, 80), Qt.AlignLeft, default_font),
            "imux_raw":      ("IMUX: -2.50", (600, 110), Qt.AlignLeft, default_font),
            "imuy_raw":      ("IMUY: -2.50", (600, 140), Qt.AlignLeft, default_font),
            "imuz_raw":      ("IMUZ: -2.50", (600, 170), Qt.AlignLeft, default_font),
            "output_shaft_raw":("OutS: 10000", (600, 210), Qt.AlignLeft, default_font),
            "odometer":      ("Miles: 000.0", (600, 240), Qt.AlignLeft, default_font),

            "bus_out_status":  ("CAN Status: 0", (290, 410), Qt.AlignLeft, default_font)
        }

        # Create and configure all labels
        for name, (text, pos, align, font) in widgets.items():
            label = QLabel(text, page)
            label.setAlignment(align)
            label.setFont(font)
            label.setStyleSheet(white_style)
            label.move(*pos)
            setattr(self, name, label)

    ''' Determine what to do with the LEDs '''
    def update_LEDs(self):
        presets = LedController.LedPresets
        can = self.canObject
        # Cache CAN values for this function. Lots of these are reused
        vals = {k: can.get(k) for k in ("RPM","Oil","Coolant","Battery","Fuel","Neutral","Speed","AeroMode","TC","WSRR","WSRL","WSFR","WSFL","TC_Comp", "TC_Cut","Brightness")}
        controller = self.ledController

        rpm = vals["RPM"]
        bat = vals["Battery"]


        #gear = vals["Gear"]
        all_row = [0,1,2,13,14,15]
        middle_row = [1,14]
        bottom_row = [0,15]

        ''' IMPORTANT: EACH BLINKING BEHAVIOR MAY ONLY BE USED IN ONE RULE. IF MULTIPLE RULES USE THE SAME BLINK, THE BLINKING WILL NOT WORK'''
        rules = [
            # Tachometer rules
            ((rpm > 9500) and (rpm <= 12500), [3,12], presets.TACH_GREEN),
            ((rpm > 10100) and (rpm <= 12500), [4,11], presets.TACH_GREEN),
            ((rpm > 10700) and (rpm <= 12500), [5,10], presets.TACH_YELLOW),
            ((rpm > 11300) and (rpm <= 12500), [6,9], presets.TACH_YELLOW),
            ((rpm > 11900) and (rpm <= 12500),[7,8], presets.TACH_RED),
            ((rpm > 12500),list(range(3,13)), presets.TACH_BLUE),
            # Warning rules
            ((0.005*vals["RPM"] > vals["Oil"] and vals["Oil"] < 60), all_row, presets.WARN_OIL),
            ((220 < vals["Coolant"] < 230), middle_row, presets.WARN_COOLANT),
            ((vals["Coolant"] > 230), middle_row, presets.WARN_COOLANT_BAD),
            ((10 > bat and rpm > 0 and 1000 >= rpm) or (12.7 > bat and (rpm == 0 or rpm > 1000)), middle_row, presets.WARN_BATTERY),
            ((35 > vals["Fuel"] and rpm > 0), middle_row, presets.WARN_FUEL),
            # Alert rules
            ((vals["Neutral"]==1 and 3 > vals["Speed"]), [13], presets.ALERT_NEUTRAL_STATIC),
            ((vals["Neutral"]==1 and vals["Speed"] > 3), all_row, presets.ALERT_NEUTRAL_DYNAMIC),
            ((vals["AeroMode"]==2), [2], presets.ALERT_LOWDRAG),
            ((vals["TC_Comp"] > 1  or vals["TC_Cut"] != 0), bottom_row, presets.ALERT_TC),
            #((vals["TC"] < 11 and (slipL > (vals["TC"]*0.01 + 1)) and (slipR > (vals["TC"]*0.01 + 1))), bottom_row, presets.ALERT_TC)
        ]

        for condition, leds, pre in rules:
            if condition:
                controller.add_behavior(leds,pre)
            else:
               controller.clear_behavior(leds,pre)

        controller.update(vals["Brightness"]) # parameter affects brightness. Setting will be added for this soon.

    # Small function to decide which update function to show
    def update_display(self):        
        match self.pages.currentIndex():
            case 1: self.update_raw()
            case 2: 
                self.page_snake.update_game()
            case _: self.update_main()

    ''' DISPLAY UPDATE FUNCTIONS '''

    def refresh_raw(self):
        #print("refreshed raw")
        self.gear_raw.setText("Gear: -")

    def update_raw(self):
        can = self.canObject
        #print("updated raw")
        gear = can.get("Gear")
        neutral = can.get("Neutral")
        gear_text = "-" if gear == 0 else f"{gear}" # - will be displayed if gear cannot be calculated by RC
        if neutral == 1:
            gear_text = "N"
        speed = can.get("Speed")
        tps = can.get("TPS")
        rpm = can.get("RPM")
        lo2 = can.get("Lambda")
        oil_pressure = can.get("Oil")
        coolant_temp = can.get("Coolant")

        WSFL = can.get("WSFL")
        WSFR = can.get("WSFR")
        WSRL = can.get("WSRL")
        WSRR = can.get("WSRR")

        tc_set = can.get("TC")
        fuel_mix = can.get("FuelMix")
        active_set = can.get("AeroMode")
        drs = can.get("DRS")
        imux = can.get("IMUX")
        imuy = can.get("IMUY")
        imuz = can.get("IMUZ")

        outshaft = can.get("Engine_Speed")
        odo = can.get("Odometer")

        fuel = can.get("Fuel")
        battery = can.get("Battery")

        fbpsi = can.get("FBrakePSI")
        rbpsi = can.get("RBrakePSI")
        steer_angle = can.get("SteerAngle")

        can_out_status = can.get("BusOut")

        
        self.gear_raw.setText(f"Gear: {gear_text}")
        self.speed_raw.setText(f"Speed: {speed}")
        self.TPS_raw.setText(f"TPS: {tps}")
        self.RPM_raw.setText(f"RPM: {rpm}")
        self.lambda_raw.setText(f"LO2: {lo2}")
        self.oil_raw.setText(f"EOP: {oil_pressure}")
        self.coolant_raw.setText(f"Coolant: {coolant_temp}")

        self.WSFL_raw.setText(f"{WSFL}")
        self.WSFR_raw.setText(f"{WSFR}")
        self.WSRL_raw.setText(f"{WSRL}")
        self.WSRR_raw.setText(f"{WSRR}")

        if tc_set > 10:
            self.tc_raw.setText("TC OFF")
        else:
            self.tc_raw.setText(f"TC: {tc_set}")

        self.mix_raw.setText(f"Fuel Mix: {fuel_mix}")
        if active_set == 0:
            active_text = "OFF"
        elif active_set == 1:
            active_text = "AUTO"
        elif active_set == 3:
            active_text = "TRIM"
        else:
            active_text = "LOW"

        self.fuel_raw.setText(f"Fuel: {fuel}")
        self.battery_raw.setText(f"Battery: {battery}")

        self.fbrake_raw.setText(f"Front Brake: {fbpsi}")
        self.rbrake_raw.setText(f"Rear Brake: {rbpsi}")
        self.steer_angle_raw.setText(f"Steering Angle: {steer_angle}")

        self.AA_set_raw.setText(f"Active Aero: {active_text}")
        if drs == 2:
            drs_text = "ON"
        else:
            drs_text = "OFF"
        self.DRS_raw.setText(f"DRS: {drs_text}")
        self.imux_raw.setText(f"Gx: {imux}")
        self.imuy_raw.setText(f"Gy: {imuy}")
        self.imuz_raw.setText(f"Gz: {imuz}")

        self.output_shaft_raw.setText(f"OutS: {outshaft}")
        self.odometer.setText(f"Miles: {odo:.1f}")


        self.bus_out_status.setText(f"CAN Status: {can_out_status}")
        

    def refresh_main(self):
        self.rpm_label.setText("   13800  ")
        self.speed_label.setText("RPM: 13800")
        self.active_setting.setText("Low-Drag")
        self.battery_label.resize(190,56)
        self.tc.setText("Low-Drag")
        self.oil_label.resize(190,56)
        self.coolant_label.resize(190,56)
        self.fuel_label.resize(190,56)
        self.fuel_mixture_label.setText("Low-Drag")
        self.active_sens_label.setText("Low-Drag")

    def update_main(self):
        can = self.canObject

        rpm = can.get("RPM")
        speed = can.get("Speed")
        gear = can.get("Gear")
        neutral = can.get("Neutral")
        gear_text = "-" if gear == 0 else f"{gear}" # - will be displayed if gear cannot be calculated by RC
        if neutral == 1:
            gear_text = "N"
        fuel_mix = can.get("FuelMix")
        fuel_text = f"+{fuel_mix}" if fuel_mix > 0 else f"{fuel_mix}"
        tc_set = can.get("TC") # TC text is handled elsewhere because the color is also updated for this specific value
        ledb = can.get("Brightness")
        active_set = can.get("AeroMode")
        active_sens = can.get("AeroSens")
        active_bal = can.get("AeroBal")
        tps = can.get("TPS")
        battery = can.get("Battery")
        lc = 1 if speed < 10 else 0
        coolant = can.get("Coolant")
        oil_pressure = can.get("Oil")
        fuel = can.get("Fuel")
        front_brake_pressure = can.get("FBrakePSI")
        bbal = can.get("BrakeBal")/10
        bbal_text = f"{bbal:.1f}" if bbal is not None and bbal != 0 else "calc..."
        aero_shift = can.get("AeroBalShift")
        # Brake bias here
        active_state = can.get("DRS")
        lo2 = can.get("Lambda")

        if active_set == 0:
            active_text = "OFF"
        elif active_set == 1:
            active_text = "AUTO"
        elif active_set == 3:
            active_text = "TRIM"
        else:
            active_text = "LOW"

        self.rpm_label.setText(f"{rpm}")
        self.speed_label.setText(f"{speed}")
        self.gear_label.setText(f"{gear_text}")
        self.active_setting.setText(f"{active_text}")
        self.battery_label.setText(f"{battery} V")
        self.tc.setText(f"{tc_set}")
        self.fuel_mixture_label.setText(f"{fuel_text}")
        self.coolant_label.setText(f"{coolant} F")
        self.oil_label.setText(f"{oil_pressure:.1F} PSI")
        self.fuel_label.setText(f"{fuel} PSI")
        # Brake bias label update
        self.tps_small.setText(f"TPS: {tps}")
        self.lambda_small.setText(f"LO2: {lo2}")

        sens_labels = ["Lazy","Safe","Balanc","Aggro","Attack"]
        self.active_sens_label.setText(f"{sens_labels[active_sens+2]}") # NEEDS TO BE FUNCTION BASED

        self.led_label.setText(f"{ledb}%")
        self.bbal_label.setText(f"{bbal_text}")
        self.aero_shift_label.setText(f"{aero_shift}")
        self.active_bal_label.setText(f"{active_bal}")
        
        # This logic may need to be reworked, but basically we indicate that floor clear is being used only if the engine
        # isn't running or cranking
        if (rpm < 100) and (tps >= 98):
            self.pending_setting_message = ("FLOOD", "CLEAR", "rgb(255, 255, 255)", 2000)


        # TC Color because it looks nice :)
        tc_color = self.tc.color
        if tc_set > 10:
            self.tc.setText("TC OFF")
            tc_color = self.white_color
        elif tc_set <= 2:
            tc_color = "rgb(20, 20, 255)"
        elif tc_set <= 7:
            tc_color = "rgb(255, 255, 20)"
        else:
            tc_color = "rgb(20, 255, 20)"
            
        # This conditional may be unnecessary
        if tc_color != self.tc.color:
            self.tc.setStyleSheet(f"""
                                        color: {tc_color};
                                        background-color: {self.black_color};
                                        border: 2px solid {tc_color};
                                        padding: 0px 3px;
                                        """)
            self.tc.color = tc_color

        fuel_mix_color = self.fuel_mixture_label.color
        if fuel_mix > 0:
            fuel_mix_color = "rgb(255, 20, 20)"
        elif fuel_mix < 0:
            fuel_mix_color = "rgb(20, 255, 20)"
        else:
            fuel_mix_color = self.white_color

        if fuel_mix_color != self.fuel_mixture_label.color:
            self.fuel_mixture_label.setStyleSheet(f"""
                                        color: {fuel_mix_color};
                                        background-color: rgba(0,0,0,0);
                                        border: 2px solid {fuel_mix_color};
                                        padding: 0px 3px;
                                        """)
            self.fuel_mixture_label.color = fuel_mix_color


        # Example of how to set up an alert rule
        '''
        if not low_bat_warn and battery < 8.5:
            low_bat_warn = True
            self.show_alert(f"Low Batt", "WARN", "rgb(220, 20, 20)", 2000)
        elif low_bat_warn and battery > 10:
            low_bat_warn = False
        '''

        # Update gear color
        if neutral == 1:
            gear_color = "rgb(20, 20, 255)"
        else:
            gear_color = f"{self.black_color}"

        if gear_color != self.gear_color:
            self.gear_label.setStyleSheet(f"""
                                          background-color: {gear_color};  
                                        color: {self.white_color};
                                        border: 2px solid {self.white_color};
                                        padding: 10px 20px;
                                        """)

        # Update the RPM bar and its color
        rpm_fill_width = int((rpm / self.max_rpm) * 800)  # Match background width
        self.rpm_bar_fill.setGeometry(0, 0, rpm_fill_width, 42)
        '''
        if rpm > 10500:
            rpm_color = "rgb(255, 20, 20)"
        elif rpm > 8500:
            rpm_color = "rgb(255, 255, 20)"
        else:
            rpm_color = "rgb(20, 255, 20)"

        if rpm_color != self.rpm_bar_color:
            self.rpm_bar_fill.setStyleSheet(f"background-color: {rpm_color}")
            self.rpm_bar_color = rpm_color
        '''

        tps_fill_height = int((tps*2.3))
        self.tps_fill.setGeometry(0, 230 - tps_fill_height, 30, 230)

        brake_fill_height = int((230*front_brake_pressure/300)) if front_brake_pressure < 300 else 230
        self.brake_fill.setGeometry(0, 230 - brake_fill_height, 30, 230)

        if self.lc.state != lc:
            if lc == 1:
                self.lc.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: rgb(20, 220, 20);
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
            else:
                self.lc.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.lc.state = lc


        if active_state != self.drs.state:
            if active_state == 2: # 2 is the state representing "Low drag" in the active aero FSM
                self.drs.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: rgb(20, 220, 20);
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
            else:
                self.drs.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     padding: 5px 11px; 
                                     """)
        self.drs.state = active_state

# Ambient alert system
    def update_ambient_alert(self):
        can = self.canObject

        coolant = can.get("Coolant")
        oil_pressure = can.get("Oil")
        rpm = can.get("RPM")
        fuel = can.get("Fuel")
        battery = can.get("Battery")

        # Handle warning display:
        # Step 1: determine if a warning should be added or removed
        # 0: coolant, 1: oil pressure, 2: fuel pressure, 3: battery low
        # Coolant
        if coolant > 220 and self.warnings[0] == 0:
            self.warning_alert_text.buffer.add("Coolant Hot")
            self.warnings[0] = 1
            self.warning_alert_background.setColor(QColor(209, 48, 27))
            self.coolant_label.setStyleSheet(f"""
                                     color: rgb(255, 20, 20);
                                     background-color: {self.black_color};
                                     border: 2px solid rgb(255, 20, 20);
                                     """)
        elif self.warnings[0] == 1 and coolant < 220:
            self.warning_alert_text.buffer.discard("Coolant Hot")
            self.warnings[0] = 0
            self.coolant_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
            
        # Oil pressure
        # Should expect to see ~ 10 PSI per 1000 RPM to an extent (max psi around 70-90 ish)
        # Therefore 0.01*rpm should be approximately equal to oil pressure.
        # If 0.01*rpm is double or more compared to the oil pressure, we should consider the pressure low
        # Pressure saturates at around 60PSI so the warning will trigger at very high RPM, so we will not warn above 60 psi
        if (oil_pressure < 0.005*rpm and oil_pressure < 60) and self.warnings[1] == 0:
            self.warning_alert_text.buffer.add("Oil PSI Low")
            self.warnings[1] = 1
            self.warning_alert_background.setColor(QColor(209, 48, 27))
            self.oil_label.setStyleSheet(f"""
                                     color: rgb(255, 20, 20);
                                     background-color: {self.black_color};
                                     border: 2px solid rgb(255, 20, 20);
                                     """)
        elif self.warnings[1] == 1 and oil_pressure > 0.005*rpm:
            self.warning_alert_text.buffer.discard("Oil PSI Low")
            self.warnings[1] = 0
            self.oil_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        # Fuel pressure
        if fuel < 35 and rpm > 0 and self.warnings[2] == 0:
            self.warning_alert_text.buffer.add("Fuel PSI Low")
            self.warnings[2] = 1
            self.fuel_label.setStyleSheet(f"""
                                     color: rgb(255, 255, 20);
                                     background-color: {self.black_color};
                                     border: 2px solid rgb(255, 255, 20);
                                     """)
        elif self.warnings[2] == 1 and fuel >= 40:
            self.warning_alert_text.buffer.discard("Fuel PSI Low")
            self.warnings[2] = 0
            self.fuel_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        # Battery warning. Checks for < 10V while cranking and < 12.7 while engine not running
            # v Cranking: RPM between 1 and 1000 v              v Running or sitting with engine off: RPM == 0 or RPM > 1000 v
        if battery < 12.7 and self.warnings[3] == 0:
            self.warning_alert_text.buffer.add("Battery Low")
            self.warnings[3] = 1
            self.battery_label.setStyleSheet(f"""
                                     color: rgb(255, 255, 20);
                                     background-color: {self.black_color};
                                     border: 2px solid rgb(255, 255, 20);
                                     """)
        elif self.warnings[3] == 1 and battery >= 12.8:
            self.warning_alert_text.buffer.discard("Battery Low")
            self.warnings[3] = 0
            self.battery_label.setStyleSheet(f"""
                                     color: {self.white_color};
                                     background-color: {self.black_color};
                                     border: 2px solid {self.white_color};
                                     """)
        
        if self.warnings[0] == 0 and self.warnings[1] == 0:
            self.warning_alert_background.setColor(QColor(189, 172, 23))


        if self.warning_alert_text.buffer:
            if not self.warning_alert_text.shown:
                self.warning_alert_background.show()
                self.warning_alert_text.show()
                self.warning_alert_text.shown = True
            warn_text = ""
            for i in self.warning_alert_text.buffer:
                warn_text += f"{i}       "
            self.warning_alert_text.setText(warn_text)
        elif self.warning_alert_text.shown:
            self.warning_alert_background.hide()
            self.warning_alert_text.hide()
            self.warning_alert_text.shown = False
            

    # Function to show the alert box with inputted information. If this function is called outside of the main event loop,
    # the alert will never disappear. Use self.pending_setting_message instead
    def show_alert(self, line1:str, line2:str, bgcolor:str, duration_millis=2000):
        self.info_alert_background.setStyleSheet(f"background-color: {bgcolor}")
        self.info_alert_background.show()
        self.info_alert_text.setText(f"{line1}\n{line2}")
        self.info_alert_text.show()
        self.alert_timer.start(duration_millis)
    def handle_pending_alert(self):
        pending = self.pending_setting_message
        if pending is not None and len(pending) == 4:
            self.show_alert(pending[0], pending[1], pending[2], pending[3])
            self.pending_setting_message = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_S:
            if self.snake_letters_typed == 0:
                self.snake_letters_typed = 1
            else: self.snake_letters_typed = 0
        elif event.key() == Qt.Key_N:
            if self.snake_letters_typed == 1:
                self.snake_letters_typed = 2
            else: self.snake_letters_typed = 0
        elif event.key() == Qt.Key_A:
            if self.snake_letters_typed == 2:
                self.snake_letters_typed = 3
            else: self.snake_letters_typed = 0
        elif event.key() == Qt.Key_K:
            if self.snake_letters_typed == 3:
                self.snake_letters_typed = 4
            else: self.snake_letters_typed = 0
        elif event.key() == Qt.Key_E:
            if self.snake_letters_typed == 4:
                index = 2
                self.pages.setCurrentIndex(index)
            self.snake_letters_typed = 0
        else:
            self.snake_letters_typed = 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Go to next page
            index = (self.pages.currentIndex() + 1) % (self.pages.count() - 1)
            self.pages.setCurrentIndex(index)    

    def on_page_switched(self):
        match self.pages.currentIndex():
            case 0: self.refresh_main()
            case 1: self.refresh_raw()
            case 2: self.page_snake.setFocus()

class WarnAlertWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setGeometry(0, 42, 800, 438)
        self.color = QColor(209, 48, 27)

    def setColor(self, new_color): # Must take in a QColor object
        self.color = new_color
        self.update() # repaint
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setBrush(self.color)     # Red
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRect(0, 0, 20, 438))

        painter.drawRect(QRect(780, 0, 800, 438))

        painter.drawRect(QRect(20, 403, 780, 438))

# Run
if __name__ == "__main__":
    print("Started main")
    try: 
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
        app = QApplication(sys.argv)
        dash = Dashboard()
        print("Dashboard initialization complete. Running dash.show()")
        try: 
            dash.show()
        except Exception as e:
            print(f"Failed to show dashboard: {e}")
        sys.exit(app.exec_())
    except Exception:
        with open("/home/terpsracing/dashboard/CRASH_LOG.txt", "w") as f:
            f.write(traceback.format_exc())