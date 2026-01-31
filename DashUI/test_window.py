import sys, random, traceback
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt, QTimer


class GameWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)

        self.setGeometry(0,0, 800, 480)

        # Game grid will be 40x24
        self.snake = [(35,12), (36,12), (37,12)]
        self.direction = [-1, 0] # First number = left/right direction, second number = up/down direction
        self.food = (15, 12)
        self.score = 0
        
        
        self.score_label = QLabel("0", self)
        self.score_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.score_label.setFont(QFont("Ubuntu", 20, QFont.DemiBold))
        self.score_label.setStyleSheet("""
            color: rgb(220, 220, 220);
            background: transparent;
        """)
        self.score_label.setFixedWidth(100)
        self.score_label.move(680, 10)
        

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_game)
        self.timer.start(100)

    def reset_game(self):
        self.snake = [(35,12), (36,12), (37,12)]
        self.direction = [-1, 0] # First number = left/right direction, second number = up/down direction
        self.food = (15, 12)
        self.score = 0
        self.score_label.setText("0")
    
    def update_game(self):
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30,30,30))

        painter.setBrush(QColor(200, 220, 200))
        for x,y in self.snake:
            painter.drawRect(x*20, y*20, 20, 20)
        
        painter.setBrush(QColor(220, 20, 20))
        fx,fy = self.food
        painter.drawRect(fx*20, fy*20, 20, 20)

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


app = QApplication(sys.argv)
game = GameWidget()
game.show()
sys.exit(app.exec_())

