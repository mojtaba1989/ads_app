import sys
import cv2
import os
from PIL import Image
import numpy as np
import json
import pandas as pd
import folium
import datetime
from geopy.distance import geodesic

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
from pages.videoProcessApp import VideoApp
from pages.scenarioApp import ScenarioApp



file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)



# def find_closest_time_utm(gps_dict, lat, lon):
#     target_x, target_y, _, _ = utm.from_latlon(lat, lon)

#     def distance_to_target(coord):
#         x, y, _, _ = utm.from_latlon(coord[0], coord[1])
#         return np.sqrt((x-target_x)**2 + (y-target_y)**2)

#     closest_time = min(gps_dict, key=lambda t: distance_to_target(gps_dict[t]))
#     return closest_time

def calculate_trip_distance(gps_dict):
    # Ensure points are sorted by time
    sorted_times = sorted(gps_dict.keys())
    gps_points = [tuple(gps_dict[t]) for t in sorted_times]

    total_km = 0
    for i in range(len(gps_points) - 1):
        total_km += geodesic(gps_points[i], gps_points[i + 1]).kilometers

    total_miles = total_km * 0.621371
    return total_km, total_miles

def find_closest_time_geopy(gps_dict, lat, lon):
    target_coord = (lat, lon)

    def distance_to_target(coord):
        return geodesic(coord, target_coord).meters

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
        
def format_time(seconds, show_hours=False):
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if show_hours or hours > 0:
        return f"{hours:02}:{mins:02}:{secs:02}"
    else:
        return f"{mins:02}:{secs:02}"
        
class Bridge(QObject):
    def __init__(self, webview, callback=None):
        super().__init__()
        self.webview = webview
        self.callback = callback

    @pyqtSlot(float, float)
    def markerMoved(self, lat, lon):
        if self.callback:
            self.callback(lat, lon)

    @pyqtSlot(float, float)
    def update_marker(self, pose):
        js = f"updateMarker({pose[0]}, {pose[1]});"
        self.webview.page().runJavaScript(js)

    @QtCore.pyqtSlot(list)
    def sendRoute(self, route):
        pass

class MainApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        self.setAttribute(QtCore.Qt.WA_QuitOnClose)
        self.setupUi(self)
        self.adjustUI()
        self.sync = {}

    def adjustUI(self):
        self.mapView = QWebEngineView(self.groupBox_2)
        self.mapView.setObjectName("mapView")
        self.gridLayout_5.addWidget(self.mapView, 0, 0, 1, 1)

        self.cap = None
        self.total_frames = 0
        self.fps = 15

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        # buttons
        self.setBut(self.playBut, 'play')
        self.playBut.setEnabled(False)
        self.playing = False
        self.setBut(self.ejectBut, 'eject')
        self.setBut(self.beginningBut, 'begining')
        self.setBut(self.rewindBut, 'rewind')
        self.setBut(self.skipBut, 'forward')
        self.setBut(self.endBut, 'end')
        self.beginningBut.setEnabled(False)
        self.rewindBut.setEnabled(False)
        self.skipBut.setEnabled(False)
        self.endBut.setEnabled(False)

        self.scenAddB.setEnabled(False)
        self.scenEditB.setEnabled(False)
        self.scenRemoveB.setEnabled(False)
        

        # connections
        self.actionOpen.triggered.connect(self.open_dads)
        self.timeCtrl.sliderMoved.connect(self.slider_moved)
        self.actionDADS_Creator_Wizard.triggered.connect(self.open_wizard)
        self.cameraSelect.currentIndexChanged.connect(self.open_video)
        self.ROStimeBox.textChanged.connect(self.update_time)
        self.playBut.clicked.connect(self.play_pause_video)
        self.skipBut.pressed.connect(self.forward_press)
        self.skipBut.released.connect(self.forward_release)
        self.ejectBut.clicked.connect(self.open_dads)
        self.scenAddB.clicked.connect(self.open_scenario_app)
        self.scenEditB.clicked.connect(self.edit_scenario)
        self.scenGoToB.clicked.connect(self.goto_scenario)
        self.scenRemoveB.clicked.connect(self.remove_scenario)
        self.scenList.itemDoubleClicked.connect(self.goto_scenario)
        self.actionSave.triggered.connect(self.save_dads)
        self.actionSave_As.triggered.connect(self.save_as_dads)


        
    # handles
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

    #video controls    
    def open_video(self):
        file_path = os.path.join(self.main_dict['pwd'], self.cameraSelect.currentText())
        self.cap = cv2.VideoCapture(file_path)
        ref_time = self.ROStimeBox.toPlainText()
        if self.cap.isOpened():
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

            self.timeCtrl.setMaximum(self.total_frames)
            self.timeCtrl.setEnabled(True)
            self.playBut.setEnabled(True)
            self.skipBut.setEnabled(True)
            self.setBut(self.playBut, 'pause')

            self.playing = True
            self.timer.start(int(1000 / self.fps))
            self.play_pause_video()
            for topic in self.main_dict['topics'].keys():
                if topic in self.cameraSelect.currentText():
                    self.sync['current'] = self.sync[topic]
                    rev = {}
                    for key in self.sync['current'].keys():
                        rev[self.sync['current'][key]] = key
                    self.sync['rev'] = rev
                    break
        if ref_time != '':
            self.slider_moved(get_closest(ref_time, self.sync['rev'])[1])

    def update_cam_select(self):
        self.cameraSelect.clear()
        for i in range(len(self.main_dict['video'])):
            self.cameraSelect.addItem(self.main_dict['video'][i])

    def open_camera_sync(self):
        self.sync = {}
        for video in self.main_dict['video']:
            for topic in self.main_dict['topics'].keys():
                if topic in video:
                    self.sync[topic] = {}
                    for key in self.main_dict['topics'][topic]:
                        data = pd.read_csv(os.path.join(self.main_dict['pwd'], 'csv', key + '.' + topic))
                        for i in range(len(data)):
                            self.sync[topic][int(data['seq'][i])] = int(data['time'][i])

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
        if frame_id in self.sync['current'].keys():
            self.ROStimeBox.setText(str(self.sync['current'][frame_id]))
        else:
            self.ROStimeBox.setText('')
        passed_time_sec = frame_id / self.fps
        remaining_time_sec = (self.total_frames - frame_id) / self.fps
        self.pasTime.setText(format_time(passed_time_sec))
        self.remTime.setText(format_time(remaining_time_sec))


    def slider_moved(self, position):
        if self.cap:
            self.timer.stop()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
            if self.playing:
                self.timer.start(int(1000 / self.fps))

    def forward_press(self):
        if self.playing:
            self.playing = True
            self.timer.start(int(1000 / self.fps / 2))
    def forward_release(self):
        if self.playing:
            self.playing = True
            self.timer.start(int(1000 / self.fps))


    ## MAP Control
    def update_marker(self, lat, lon):
        new = find_closest_time_geopy(self.gps, lat, lon)
        self.ROStimeBox.setText(str(new))
        new_frame = get_closest(str(new), self.sync['rev'])[1]
        self.slider_moved(int(new_frame))

    def open_map(self):
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "map.html"))
        self.mapView.setUrl(QtCore.QUrl.fromLocalFile(file_path))

        self.channel = QWebChannel()
        self.bridge = Bridge(self.mapView, self.update_marker)
        self.channel.registerObject('bridge', self.bridge)
        self.mapView.page().setWebChannel(self.channel)

        route = [[lat, lon] for lat, lon in self.gps.values()]
        js_array = str(route).replace("'", "")  # Simple conversion to JS array format

        js = f"setRoute({js_array});"
        QTimer.singleShot(2000, lambda: self.mapView.page().runJavaScript(js))
    
    def open_gps(self):
        self.gps = {}
        for file in self.main_dict['topics']['pos']:
            file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.pos')
            data = pd.read_csv(file_path)
            for i in range(len(data)):
                self.gps[int(data['time'][i])] = [float(data['lat'][i]), float(data['lon'][i])]


    # Scenario Control
    def load_scenarios(self):
        self.scenList.clear()
        self.clean_up_scenarios()
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            self.scenList.addItem(f'{tmp[0]}, {tmp[2]}: {tmp[1]}')
        if 'additional_scenarios' not in self.main_dict.keys():
            self.main_dict['additional_scenarios'] = []          
    
    def open_scenario_app(self):
        if self.NOW == -1:
            return
        self.scenario_app = ScenarioApp(time_now=self.NOW,
                                         callback=self.add_from_scenario_app,
                                         additional=self.main_dict['additional_scenarios'])
        self.scenario_app.show()

    def add_from_scenario_app(self, time, scenario, add_scenario=None):
        if add_scenario is not None and add_scenario not in self.main_dict['additional_scenarios']:
            self.main_dict['additional_scenarios'].append(add_scenario)
        time_p = datetime.datetime.fromtimestamp(float(time)/1e9).strftime('%H:%M:%S.%f')[:-3]
        id = self.scenList.count() + 1
        self.main_dict['scenarios'][time] = (id, scenario, time_p)  # time, scenario
        self.clean_up_scenarios()
        self.scenList.clear()
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            self.scenList.addItem(f'{tmp[0]}, {tmp[2]}: {tmp[1]}')

    def edit_scenario(self):
        id = self.scenList.currentRow()+1
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            if tmp[0] == id:
                self.scenario_app = ScenarioApp(time_now=key,
                                                scenario=tmp[1],
                                                callback=self.add_from_scenario_app,
                                                additional=self.main_dict['additional_scenarios'])
                self.scenario_app.show()
    
    def remove_scenario(self):
        id = self.scenList.currentRow()+1
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            if tmp[0] == id:
                del self.main_dict['scenarios'][key]
                self.clean_up_scenarios()
                self.scenList.clear()
                break
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            self.scenList.addItem(f'{tmp[0]}, {tmp[2]}: {tmp[1]}')


    def goto_scenario(self):
        id = self.scenList.currentRow()+1
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            if tmp[0] == id:
                self.ROStimeBox.setText(str(key))
                new_frame = get_closest(str(key), self.sync['rev'])[1]
                self.slider_moved(int(new_frame))
                return

    def clean_up_scenarios(self):
        tmp = self.main_dict['scenarios']
        self.main_dict['scenarios'] = {}
        time_list = list(tmp.keys())
        time_list.sort()
        for id, time in enumerate(time_list):
            self.main_dict['scenarios'][time] = (id+1, tmp[time][1], tmp[time][2])



    #### General  
    def refresh(self):
        if self.playing:
            self.play_pause_video()
        
        try:
            self.cap.release()
        except:
            pass
        self.timer.stop()
        self.cap = None
        self.total_frames = 0

        self.playBut.setEnabled(False)
        self.setBut(self.playBut, 'play')
        self.timeCtrl.blockSignals(True)
        self.timeCtrl.setValue(0)
        self.timeCtrl.blockSignals(False)
        self.cameraSelect.clear()
        
        self.scenList.clear()
        self.ROStimeBox.setText('')
        self.DTBox.setText('')
        self.NOW = -1
        self.FILENAME = ''
        self.main_dict = {}
        self.sync = {}
        self.gps = {}

      
    def update_time(self):
        try:
            self.NOW = int(self.ROStimeBox.toPlainText())
            self.DTBox.setText(str(datetime.datetime.fromtimestamp(float(self.NOW)/1e9)))
            self.bridge.update_marker(get_closest(self.NOW, self.gps)[1])
        except:
            self.NOW = -1

    def extract_info(self):
        if not 'info' in self.main_dict.keys():
            time_array = np.array([float(key) for key in self.gps.keys()])
            time_array = time_array/1e9
            info = {}
            starting_time = datetime.datetime.fromtimestamp(np.min(time_array))
            info['starting time'] = str(starting_time)
            info['trip duration (s)'] = str(int(np.max(time_array)-np.min(time_array)))
            info['trip duration'] = format_time(int(time_array[-1]-time_array[0]))
            info['traveled distance Km'] = f'{calculate_trip_distance(self.gps)[0]:.2f}'
            info['traveled distance mi'] = f'{calculate_trip_distance(self.gps)[1]:.2f}'
            self.main_dict['info'] = info
        for key in self.main_dict['info'].keys():
            description = self.main_dict['info'][key]
            self.infoL.addItem(f'{key}: {description}')
        
    
    def load(self):
        self.open_camera_sync()
        self.open_gps()
        self.update_cam_select()
        self.open_video()
        self.open_map()
        self.extract_info()
        self.load_scenarios()

    def unlockBut(self):
        self.scenAddB.setEnabled(True)
        self.scenEditB.setEnabled(True)
        self.scenRemoveB.setEnabled(True)
        
    def open_dads(self):
        self.refresh()
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(caption="Open DADS File", filter="Trip Files (*.DADS)")
        if file_path == "":
            return
        dir_name = os.path.dirname(file_path)
        self.FILENAME = file_path
        self.main_dict = {}
        with open(file_path, 'r') as f:
            self.main_dict = json.load(f)
        self.main_dict['pwd'] = dir_name
        if 'scenarios' not in self.main_dict.keys():
            self.main_dict['scenarios'] = {}
        self.load()
        self.unlockBut()

    def save_dads(self):
        with open(self.FILENAME, 'w') as f:
            json.dump(self.main_dict, f, indent=4)

    def save_as_dads(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(caption="Save File", filter="Trip Files (*.DADS)")
        if file_path == "":
            return
        self.FILENAME = file_path
        self.save_dads()

    def open_wizard(self):
        self.wizard_window = WizardApp(parent=self)
        self.wizard_window.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())