import sys
import cv2
import os
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(900, 541)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.Ctrl = QtWidgets.QGroupBox(self.centralwidget)
        self.Ctrl.setGeometry(QtCore.QRect(10, 400, 881, 101))
        self.Ctrl.setObjectName("Ctrl")
        self.timeCtrl = QtWidgets.QSlider(self.Ctrl)
        self.timeCtrl.setGeometry(QtCore.QRect(30, 30, 841, 22))
        self.timeCtrl.setOrientation(QtCore.Qt.Horizontal)
        self.timeCtrl.setObjectName("timeCtrl")
        self.replayBut = QtWidgets.QPushButton(self.Ctrl)
        self.replayBut.setGeometry(QtCore.QRect(830, 60, 40, 31))
        self.replayBut.setObjectName("replayBut")
        self.pauseBut = QtWidgets.QPushButton(self.Ctrl)
        self.pauseBut.setGeometry(QtCore.QRect(643, 60, 41, 31))
        self.pauseBut.setObjectName("pauseBut")
        self.skipBut = QtWidgets.QPushButton(self.Ctrl)
        self.skipBut.setGeometry(QtCore.QRect(736, 60, 41, 31))
        self.skipBut.setObjectName("skipBut")
        self.begginingBut = QtWidgets.QPushButton(self.Ctrl)
        self.begginingBut.setGeometry(QtCore.QRect(549, 60, 41, 31))
        self.begginingBut.setObjectName("begginingBut")
        self.playBut = QtWidgets.QPushButton(self.Ctrl)
        self.playBut.setGeometry(QtCore.QRect(690, 60, 40, 31))
        self.playBut.setObjectName("playBut")
        self.rewindBut = QtWidgets.QPushButton(self.Ctrl)
        self.rewindBut.setGeometry(QtCore.QRect(596, 60, 41, 31))
        self.rewindBut.setObjectName("rewindBut")
        self.endBut = QtWidgets.QPushButton(self.Ctrl)
        self.endBut.setGeometry(QtCore.QRect(783, 60, 41, 31))
        self.endBut.setObjectName("endBut")
        self.Camera = QtWidgets.QGroupBox(self.centralwidget)
        self.Camera.setGeometry(QtCore.QRect(10, 80, 531, 311))
        self.Camera.setObjectName("Camera")
        self.cameaDisplay = QtWidgets.QLabel(self.Camera)
        self.cameaDisplay.setGeometry(QtCore.QRect(10, 60, 481, 241))
        self.cameaDisplay.setObjectName("cameaDisplay")
        self.cameraSelect = QtWidgets.QComboBox(self.Camera)
        self.cameraSelect.setGeometry(QtCore.QRect(10, 20, 501, 22))
        self.cameraSelect.setObjectName("cameraSelect")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 900, 21))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionOpen = QtWidgets.QAction(MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.menuFile.addAction(self.actionOpen)
        self.menubar.addAction(self.menuFile.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        self.adjustUI()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.Ctrl.setTitle(_translate("MainWindow", "Control"))
        self.replayBut.setText(_translate("MainWindow", "Play"))
        self.pauseBut.setText(_translate("MainWindow", "Play"))
        self.skipBut.setText(_translate("MainWindow", "Play"))
        self.begginingBut.setText(_translate("MainWindow", "Play"))
        self.playBut.setText(_translate("MainWindow", "Play"))
        self.rewindBut.setText(_translate("MainWindow", "Play"))
        self.endBut.setText(_translate("MainWindow", "Play"))
        self.Camera.setTitle(_translate("MainWindow", "Camera"))
        self.cameaDisplay.setText(_translate("MainWindow", "TextLabel"))
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.actionOpen.setText(_translate("MainWindow", "Open"))

    
    def adjustUI(self):
        self.cap = None
        self.total_frames = 0
        self.fps = 15

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        # play but
        self.setBut(self.playBut, 'play.png')
        self.playBut.setEnabled(False)
        self.playBut.clicked.connect(self.play_pause_video)
        self.playing = False

        # connections
        self.actionOpen.triggered.connect(self.open_video)
        self.timeCtrl.sliderMoved.connect(self.slider_moved)

    def setBut(self, obj, icon):
        root, ext = os.path.splitext(icon)
        if ext == "":
            icon += '.png'
        elif ext == '.png':
            pass
        else:
            exit(10)
        icon_file = os.path.join(dir_path, 'icons', icon)
        obj.setText("")
        obj.setIcon(QtGui.QIcon(icon_file))
    
    def open_video(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(caption="Open Video File", filter="Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_path == "":
            return
        self.cap = cv2.VideoCapture(file_path)
        if self.cap.isOpened():
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

            self.timeCtrl.setMaximum(self.total_frames)
            self.timeCtrl.setEnabled(True)
            self.playBut.setEnabled(True)

            self.playing = True
            self.timer.start(int(1000 / self.fps))

    def play_pause_video(self):
            if self.playing:
                self.playing = False
                self.timer.stop()
                self.setBut(self.playBut, 'pause')
            else:
                self.playing = True
                self.timer.start(int(1000 / self.fps))
                self.setBut(self.playBut, 'play')

    def next_frame(self):
        if self.cap.isOpened() and self.playing:
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
                current_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.timeCtrl.blockSignals(True)
                self.timeCtrl.setValue(current_pos)
                self.timeCtrl.blockSignals(False)
            else:
                self.timer.stop()
                self.cap.release()
    
    def display_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        image = image.resize((800, 450))

        frame_array = np.array(image)
        height, width, channel = frame_array.shape
        bytes_per_line = 3 * width
        qimg = QImage(frame_array.data, width, height, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qimg)
        self.cameaDisplay.setPixmap(pixmap)

    def slider_moved(self, position):
        if self.cap:
            self.timer.stop()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
            if self.playing:
                self.timer.start(int(1000 / self.fps))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
