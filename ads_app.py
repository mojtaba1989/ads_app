import sys
import cv2
import os
from PIL import Image
import numpy as np
import json
import pandas as pd
import folium

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWebChannel import QWebChannel

from pages.design import Ui_MainWindow
from pages.wizardApp import WizardApp


file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

import utm
from math import hypot

def find_closest_time_utm(gps_dict, lat, lon):
    target_x, target_y, _, _ = utm.from_latlon(lat, lon)

    def distance_to_target(coord):
        x, y, _, _ = utm.from_latlon(coord[0], coord[1])
        return hypot(x - target_x, y - target_y)

    closest_time = min(gps_dict, key=lambda t: distance_to_target(gps_dict[t]))
    return closest_time

def find_closest_frame(frame_dict, time):
    closest_frame = min(frame_dict, key=lambda f: abs(int(f) - int(time)))
    return closest_frame

def get_closest(key, dict):
        try:return dict[key]
        except:
            key_n = min(dict.keys(), key=lambda x: abs(int(x) - int(key)))
            return key_n, dict[key_n]
        
class Bridge(QObject):
    def __init__(self, webview, callback=None):
        super().__init__()
        self.webview = webview
        self.callback = callback

    @pyqtSlot(float, float)
    def markerMoved(self, lat, lon):
        # print(f"Marker moved to: {lat}, {lon}")
        if self.callback:
            self.callback(lat, lon)

    @pyqtSlot(float, float)
    def update_marker(self, pose):
        js = f"updateMarker({pose[0]}, {pose[1]});"
        self.webview.page().runJavaScript(js)
class MainApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        self.setAttribute(QtCore.Qt.WA_QuitOnClose)
        self.setupUi(self)
        self.adjustUI()
        self.sync = {}

    def adjustUI(self):
        self.cap = None
        self.total_frames = 0
        self.fps = 15

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        # play but
        self.setBut(self.playBut, 'play')
        self.playBut.setEnabled(False)
        self.playBut.clicked.connect(self.play_pause_video)
        self.playing = False

        # connections
        self.actionOpen.triggered.connect(self.open_dads)
        self.timeCtrl.sliderMoved.connect(self.slider_moved)
        self.actionDADS_Creator_Wizard.triggered.connect(self.open_wizard)
        self.cameraSelect.currentIndexChanged.connect(self.open_video)
        self.ROStimeBox.textChanged.connect(self.update_time)

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
        file_path = os.path.join(self.main_dict['dir'], self.cameraSelect.currentText())
        self.cap = cv2.VideoCapture(file_path)
        if self.cap.isOpened():
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

            self.timeCtrl.setMaximum(self.total_frames)
            self.timeCtrl.setEnabled(True)
            self.playBut.setEnabled(True)
            self.setBut(self.playBut, 'pause')

            self.playing = True
            self.timer.start(int(1000 / self.fps))
            for topic in self.main_dict['topics'].keys():
                if topic in self.cameraSelect.currentText():
                    self.sync['C'] = self.sync[topic]
                    break
    def update_cam_select(self):
        self.cameraSelect.clear()
        for i in range(len(self.main_dict['video'])):
            self.cameraSelect.addItem(self.main_dict['video'][i])
    
    def update_marker(self, lat, lon):
        new = find_closest_time_utm(self.gps, lat, lon)
        self.ROStimeBox.setText(str(new))
        new_frame = find_closest_frame(self.sync['C'], new)
        self.slider_moved(int(new_frame))

    def open_map(self):
        # file_path = os.path.join(self.main_dict['dir'], self.main_dict['map'])
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "map.html"))
        self.mapView.setUrl(QtCore.QUrl.fromLocalFile(file_path))

        self.channel = QWebChannel()
        self.bridge = Bridge(self.mapView, self.update_marker)
        self.channel.registerObject('bridge', self.bridge)
        self.mapView.page().setWebChannel(self.channel)

    def open_camera_sync(self):
        self.sync = {}
        for video in self.main_dict['video']:
            for topic in self.main_dict['topics'].keys():
                if topic in video:
                    self.sync[topic] = {}
                    for key in self.main_dict['topics'][topic]:
                        data = pd.read_csv(os.path.join(self.main_dict['dir'], 'csv', key + '.' + topic))
                        for i in range(len(data)):
                            self.sync[topic][data['seq'][i]] = data['time'][i]
    
    def open_gps(self):
        self.gps = {}
        for file in self.main_dict['topics']['gps']:
            file_path = os.path.join(self.main_dict['dir'], 'csv', file + '.gps')
            data = pd.read_csv(file_path)
            for i in range(len(data)):
                self.gps[int(data['time'][i])] = [float(data['latitude'][i]), float(data['longitude'][i])]

    
    def update_time(self):
        try:
            self.NOW = int(self.ROStimeBox.toPlainText())
            self.bridge.update_marker(get_closest(self.NOW, self.gps)[1])  
        except:
            self.NOW = -1
    
    def load(self):
        self.open_camera_sync()
        self.open_gps()
        self.update_cam_select()
        self.open_video()
        self.open_map()
        
    def open_dads(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(caption="Open DADS File", filter="Trip Files (*.DADS)")
        if file_path == "":
            return
        dir_name = os.path.dirname(file_path)
        self.main_dict = {}
        with open(file_path, 'r') as f:
            self.main_dict = json.load(f)
        self.main_dict['dir'] = dir_name
        self.load()

    def play_pause_video(self):
            if self.playing:
                self.playing = False
                self.timer.stop()
                self.setBut(self.playBut, 'play')
            else:
                self.playing = True
                self.timer.start(int(1000 / self.fps))
                self.setBut(self.playBut, 'pause')

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

        frame_id = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        if frame_id in self.sync['C'].keys():
            self.ROStimeBox.setText(str(self.sync['C'][frame_id]))
        else:
            self.ROStimeBox.setText('')

    def slider_moved(self, position):
        if self.cap:
            self.timer.stop()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
            if self.playing:
                self.timer.start(int(1000 / self.fps))

    def open_wizard(self):
        self.wizard_window = WizardApp(parent=self)
        self.wizard_window.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())