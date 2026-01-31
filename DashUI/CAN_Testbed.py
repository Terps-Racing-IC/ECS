from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget
from PyQt5.QtCore import QTimer, Qt, QRect
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QFont, QPainter, QColor, QCursor
import sys
import random
import struct


'''
########################################################

                    CAN INTEGRATION 

########################################################
'''

import can
can.rc['interface'] = 'socketcan'
can.rc['channel'] = 'can0'
can.rc['bitrate'] = 1000000
from can.interface import Bus

# CAN storage class that contains a dictionary of various CAN values. This way values are stored in a common location so that
# all dashboard pages can access them when needed.
class CanCommon:
    def __init__(self): 
        # Create a dict of values to store the current inputs
        self.rx_addresses = []
        self.tx_addresses = []
        self.tx = {}
        self.rx = {} # these are dicts of the form {message.arbitration_id, message.data}
        self.bus = Bus()

# Adds a value to the stored CAN values. Values are in the format of a python dict, for example {"a": 1} stores that key a = 1
    #def update_(self, data: dict):
    #    self.values.update(data)

# Returns the value associated with the given key (or None if the key does not exist)
    def get_rx(self, key, default=0):
        return self.rx.get(key, default)
    
    def get_tx(self, key, default=0):
        return self.tx.get(key, default)
    
    def clear(self):
        self.tx_addresses = []
        self.rx_addresses = []
        self.tx = {}
        self.rx = {}
    
    def poll(self):
        #print("polling CAN")
        while True:
            message = self.bus.recv(timeout=0)
            if not message:
                #print("no messages")
                break
            if message.arbitration_id not in self.rx_addresses:
                self.rx_addresses.append(message.arbitration_id)
            self.rx.update({message.arbitration_id, message.data})
            
    # Note:
    # int.from_bytes is only needed in the case of a string of bytes
    # representing an integer, not for a single byte. "big" indicates that the bytes are expected to be in Big Endian format, i.e the hex
    # number 0x12345678 is represented as 12 34 56 78 in big endian format (so index 0 has 12, index 1 has 34, etc...) whereas they
    # are ordered 78 56 34 12 in little endian format (which is commonly used in modern computer memory addressing).


'''
##################################################

                DISPLAY CODE

##################################################
'''

class CANTestBed(QWidget):
    def __init__(self):
        super().__init__()

        # Create CAN
        self.can_object = CanCommon()

        # UI setup
        self.setWindowTitle("Test Bed")
        self.resize(1280, 720)


        # Labels for clarity
        self.rx_label = QLabel("RX Addresses:")
        self.rx_label.setAlignment(Qt.AlignLeft)
        self.rx_label.setFont(QFont('Ubuntu', 30, QFont.DemiBold))
        self.rx_label.setStyleSheet(f"""
                                     color: rgb(255, 255, 255);
                                     """)
        self.rx_label.move(20, 20)

        self.tx_label = QLabel("TX Addresses:")
        self.tx_label.setAlignment(Qt.AlignLeft)
        self.tx_label.setFont(QFont('Ubuntu', 30, QFont.DemiBold))
        self.tx_label.setStyleSheet(f"""
                                     color: rgb(255, 255, 255);
                                     """)
        self.tx_label.move(20, self.height() *0.5)

        self.bytes_label = QLabel("Displaying data as # Bytes")
        self.bytes_label.setAlignment(Qt.AlignLeft)
        self.bytes_label.setFont(QFont('Ubuntu', 30, QFont.DemiBold))
        self.bytes_label.setStyleSheet(f"""
                                     color: rgb(255, 255, 255);
                                     """)
        self.bytes_label.move(self.width() - 200, 20)

        self.bytes = 1

        # Start periodic updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_lists())
        self.timer.start(40)  # Run every 40ms

        # Example data
        self.counter = 0

    def update_lists(self):
        """This is your periodic function."""
        self.counter += 1

        self.can_object.poll()
        # Example: generate new data
        rx_adds = self.can_object.rx_addresses
        tx_adds = []

        # Update the displays
        rx_text = ""
        tx_text = ""
        for address in rx_adds:
            rx_text = rx_text + f"\n{address}:"
            match self.bytes:
                case 1:
                    for byte in self.can_object.get_rx(address):
                        rx_text = rx_text + f" {byte}"
                case _:
                    continue # Unimplemented: add ways to parse data multiple bytes at a time
        for address in tx_adds:
            tx_text = tx_text + f"\n{address}:"
            match self.bytes:
                case 1:
                    for byte in self.can_object.get_rx(address):
                        tx_text = tx_text + f" {byte}"
                case _:
                    continue # Unimplemented: add ways to parse data multiple bytes at a time
            

        self.rx_label.setText("RX Addresses:" + rx_text)
        self.tx_label.setText("TX Addresses:" + tx_text)

    def refresh_list(self, widget, data):
        """Helper to refresh a QListWidget from a list."""
        widget.clear()
        widget.addItems(data)


    def keyPressEvent(self, event):
        if event.key == Qt.Key_1:
            self.bytes = 1
        elif event.key == Qt.Key_2:
            self.bytes = 2
        elif event.key == Qt.Key_4:
            self.bytes = 4
        elif event.key == Qt.Key_8:
            self.bytes = 8
        elif event.key == Qt.Key_C:
            self.can_object.clear()
        self.bytes_label.setText(f"Displaying as {self.bytes} bytes")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CANTestBed()
    window.show()
    sys.exit(app.exec_())