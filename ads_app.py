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
from contextlib import contextmanager

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWebChannel import QWebChannel

import pyqtgraph as pg

from pages.design import Ui_MainWindow
from pages.wizardApp import WizardApp
from pages.videoProcessApp import VideoApp
from pages.scenarioApp import ScenarioApp
from pages.plotApp import PlotApp
from pages.bagToCsvApp import BagToCsvApp
from pages.aboutPage import aboutPage



file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)


def calculate_trip_distance(gps_dict):
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
    def map_current_position_callback(self, pose):
        js = f"updateMarker({pose[0]}, {pose[1]});"
        self.webview.page().runJavaScript(js)

    @QtCore.pyqtSlot(list)
    def sendRoute(self, route):
        pass

class SelectablePlotWidget(QtWidgets.QFrame):
    marker_moved = pyqtSignal(float)

    def __init__(self, selection_manager, index, parent=None):
        super().__init__(parent)
        self.selection_manager = selection_manager
        self.index = index
        self.x_range = None
        self.y_range = None

        self.setStyleSheet("QFrame { background-color: transparent; border: 2px solid transparent; }")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.layout.addWidget(self.plot_widget)

        self.vline = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen('k', width=2))
        self.plot_widget.addItem(self.vline)
        self.vline.sigPositionChanged.connect(self.on_vline_moved)

        self.plot_widget.scene().sigMouseClicked.connect(self.on_click)

        self.hover_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('g', width=1, style=QtCore.Qt.DashLine))
        self.plot_widget.addItem(self.hover_line)
        self.label = pg.TextItem("", anchor=(0, 1))
        self.plot_widget.addItem(self.label)

        self.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)

        self._x = []
        self._y = []

    def plot(self, x, y, **kwargs):
        self._x = x
        self._y = y
        self.plot_widget.plot(x, y, **kwargs)

    def on_mouse_moved(self, pos):
        vb = self.plot_widget.getViewBox()
        y_pos = (3.5 * vb.viewRange()[1][1] + 1.5 * vb.viewRange()[1][0]) / 5
        if vb.sceneBoundingRect().contains(pos):
            mouse_point = vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            self.hover_line.setPos(x_val)

            if self._x:
                index = np.abs(np.array(self._x) - x_val).argmin()
                y_val = self._y[index]
                self.label.setText(f"x={self._x[index]:.2f}\ny={y_val:.2f}")
                self.label.setPos(self._x[index], y_pos)

    def on_click(self, event):
        self.selection_manager.select(self)

    def set_selected(self, selected):
        if selected:
            self.setStyleSheet("QFrame { background-color: #e8f0ff; border: 2px solid #0078d4; }")
        else:
            self.setStyleSheet("QFrame { background-color: transparent; border: 2px solid transparent; }")

    @contextmanager
    def block_signal(self):
        self._block_marker_signal = True
        yield
        self._block_marker_signal = False
    
    def map_current_position_callback(self, pose):
        with self.block_signal():
            self.vline.setPos(pose)

    def on_vline_moved(self):
        if not self._block_marker_signal:
            pos = self.vline.value()
            self.marker_moved.emit(pos)

    def reset_view(self):
        if self.x_range:
            self.plot_widget.setXRange(*self.x_range)
        if self.y_range:
            self.plot_widget.setYRange(*self.y_range)


class SelectionManager:
    def __init__(self):
        self.current = None

    def select(self, widget):
        if self.current and self.current != widget:
            self.current.set_selected(False)
        widget.set_selected(True)
        self.current = widget

    def get_selected_index(self):
        if self.current:
            return self.current.index
        return None



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

        self.scrollLayout = QtWidgets.QVBoxLayout(self.plotContents)
        self.scrollLayout.setContentsMargins(0,0,0,0)
        
        self.toolbar = QtWidgets.QToolBar()
        self.horizontalLayout_5.insertWidget(0, self.toolbar)
        self.selection_manager = SelectionManager()

        self.cap = None
        self.total_frames = 0
        self.fps = 15

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.video_next_frame)

        # buttons
        self.setIcon(self.playBut, 'play')
        self.playBut.setEnabled(False)
        self.playing = False
        self.setIcon(self.ejectBut, 'eject')
        self.setIcon(self.beginningBut, 'begining')
        self.setIcon(self.rewindBut, 'rewind')
        self.setIcon(self.skipBut, 'forward')
        self.setIcon(self.endBut, 'end')
        self.beginningBut.setEnabled(False)
        self.rewindBut.setEnabled(False)
        self.skipBut.setEnabled(False)
        self.endBut.setEnabled(False)

        self.main_button_set_all(False)
        

        # connections
        self.actionOpen.triggered.connect(self.open_dads)
        self.timeCtrl.sliderMoved.connect(self.video_slider_moved_callback)
        self.actionDADS_Creator_Wizard.triggered.connect(self.add_on_open_dads_wizard)
        self.actionBag_to_CSV.triggered.connect(self.add_on_open_bag_to_csv)
        self.actionImage_processing.triggered.connect(self.add_on_open_video_edit)
        self.actionAbout_US.triggered.connect(self.add_on_open_about)
        self.cameraSelect.currentIndexChanged.connect(self.video_load)
        self.ROStimeBox.textChanged.connect(self.main_wallclock_update)
        self.playBut.clicked.connect(self.video_play_callback)
        self.skipBut.pressed.connect(self.video_fast_forward_pressed)
        self.skipBut.released.connect(self.video_fast_forward_released)
        self.ejectBut.clicked.connect(self.open_dads)
        self.scenAddB.clicked.connect(self.scenario_app_open)
        self.scenEditB.clicked.connect(self.scenario_edit)
        self.scenGoToB.clicked.connect(self.scenario_goto_callback)
        self.scenRemoveB.clicked.connect(self.scenario_remove)
        self.scenList.itemDoubleClicked.connect(self.scenario_goto_callback)
        self.actionSave.triggered.connect(self.save_dads)
        self.actionSave_As.triggered.connect(self.save_as_dads)
        self.remPlotB.clicked.connect(self.plot_remove)
        self.addPlotB.clicked.connect(self.plot_app_open)
        self.resetPlotB.clicked.connect(self.reset_plots)

    
    # handles
    def setIcon(self, obj, icon):
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
    
    # Plots
    def plot_add_new(self, x, y, legend, index=None):
        canvas = SelectablePlotWidget(self.selection_manager, index)
        canvas.setMinimumHeight(200)
        canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        pen = pg.mkPen(color=(0, 71, 171), width=1)
        canvas.plot_widget.addLegend(offset=(-2, 2))
        canvas.plot(x, y, pen=pen, name=legend)
        canvas.plot_widget.setLabel("bottom", "Time (ns)")
        canvas.y_range = [min(y), max(y)]
        canvas.marker_moved.connect(self.plot_marker_moved_callback)
        canvas.map_current_position_callback(x[0])
        self.plot_obj_list.append(canvas)
        self.scrollLayout.addWidget(canvas)
        canvas.reset_view()

    def plot_marker_moved_callback(self, time_value):
        self.ROStimeBox.setText(str(int(time_value)))
        new_frame = get_closest(str(int(time_value)), self.sync['rev'])[1]
        self.video_slider_moved_callback(int(new_frame))

    def plot_list_update(self, new_dict):
        self.main_dict = new_dict
        self.plot_load()

    def plot_remove(self):
        selected_plot = self.selection_manager.current
        if selected_plot:
            self.scrollLayout.removeWidget(selected_plot)
            idx = self.selection_manager.get_selected_index()
            selected_plot.deleteLater()
            self.selection_manager.current = None
            self.main_dict['plots'].pop(idx)

    def plot_remove_all(self):
        for i in reversed(range(self.scrollLayout.count())):
            self.scrollLayout.itemAt(i).widget().deleteLater()
        self.selection_manager.current = None
        self.plot_obj_list = []
    
    def reset_plots(self):
        for obj in self.plot_obj_list:
            obj.reset_view()

    def plot_app_open(self):
        self.plot_app_wizard = PlotApp(self.main_dict, self.plot_list_update)
        self.plot_app_wizard.show()

    def plot_load(self):
        self.plot_remove_all()
        for plt in self.main_dict['plots']:
            time = []
            y = []
            for file in self.main_dict['topics'][plt[1]]:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + plt[1])
                data = pd.read_csv(file_path)
                if plt[2] in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        y.append(data[plt[2]][i])
                else:
                    continue
            self.plot_add_new(time, y, plt[2], plt[0])

    #video controls    
    def video_load(self):
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
            self.setIcon(self.playBut, 'pause')

            self.playing = True
            self.timer.start(int(1000 / self.fps))
            self.video_play_callback()
            for topic in self.main_dict['topics'].keys():
                if topic in self.cameraSelect.currentText():
                    self.sync['current'] = self.sync[topic]
                    rev = {}
                    for key in self.sync['current'].keys():
                        rev[self.sync['current'][key]] = key
                    self.sync['rev'] = rev
                    break
        if ref_time != '':
            self.video_slider_moved_callback(get_closest(ref_time, self.sync['rev'])[1])

    def video_camera_select(self):
        self.cameraSelect.clear()
        for i in range(len(self.main_dict['video'])):
            self.cameraSelect.addItem(self.main_dict['video'][i])

    def video_camera_sync(self):
        self.sync = {}
        for video in self.main_dict['video']:
            for topic in self.main_dict['topics'].keys():
                if topic in video:
                    self.sync[topic] = {}
                    for key in self.main_dict['topics'][topic]:
                        data = pd.read_csv(os.path.join(self.main_dict['pwd'], 'csv', key + '.' + topic))
                        for i in range(len(data)):
                            self.sync[topic][int(data['seq'][i])] = int(data['time'][i])

    def video_play_callback(self):
            if self.playing:
                self.playing = False
                self.timer.stop()
                self.setIcon(self.playBut, 'play')
            else:
                self.playing = True
                self.timer.start(int(1000 / self.fps))
                self.setIcon(self.playBut, 'pause')

    def video_next_frame(self):
        if self.cap.isOpened() and self.playing:
            ret, frame = self.cap.read()
            if ret:
                self.video_display(frame)
                current_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.timeCtrl.blockSignals(True)
                self.timeCtrl.setValue(current_pos)
                self.timeCtrl.blockSignals(False)
            else:
                self.timer.stop()
                self.cap.release()
    
    def video_display(self, frame):
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
        try:
            self.ROStimeBox.setText(str(self.sync['current'][frame_id]))
            for obj in self.plot_obj_list:
                with obj.block_signal():
                    obj.map_current_position_callback(self.sync['current'][frame_id])
        except KeyError:
            self.ROStimeBox.setText('')
        passed_time_sec = frame_id / self.fps
        remaining_time_sec = (self.total_frames - frame_id) / self.fps
        self.pasTime.setText(format_time(passed_time_sec))
        self.remTime.setText(format_time(remaining_time_sec))


    def video_slider_moved_callback(self, position):
        if self.cap:
            self.timeCtrl.blockSignals(True)
            self.timeCtrl.setValue(position)
            self.timeCtrl.blockSignals(False)
            self.timer.stop()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ret, frame = self.cap.read()
            if ret:
                self.video_display(frame)
            if self.playing:
                self.timer.start(int(1000 / self.fps))
            # for obj in self.scrollLayout.children():
            #     obj.marker_update(self.sync['current'][position])


    def video_fast_forward_pressed(self):
        if self.playing:
            self.playing = True
            self.timer.start(int(1000 / self.fps / 2))
    def video_fast_forward_released(self):
        if self.playing:
            self.playing = True
            self.timer.start(int(1000 / self.fps))


    ## MAP Control
    def map_current_position_callback(self, lat, lon):
        new = find_closest_time_geopy(self.gps, lat, lon)
        # self.ROStimeBox.setText(str(new))
        new_frame = get_closest(str(new), self.sync['rev'])[1]
        self.video_slider_moved_callback(int(new_frame))

    def map_load(self):
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "map.html"))
        self.mapView.setUrl(QtCore.QUrl.fromLocalFile(file_path))

        self.channel = QWebChannel()
        self.bridge = Bridge(self.mapView, self.map_current_position_callback)
        self.channel.registerObject('bridge', self.bridge)
        self.mapView.page().setWebChannel(self.channel)

        route = [[lat, lon] for lat, lon in self.gps.values()]
        js_array = str(route).replace("'", "")  # Simple conversion to JS array format

        js = f"setRoute({js_array});"
        QTimer.singleShot(2000, lambda: self.mapView.page().runJavaScript(js))
    
    def map_generate_gps_dictionary(self):
        self.gps = {}
        for file in self.main_dict['topics']['pos']:
            file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.pos')
            data = pd.read_csv(file_path)
            for i in range(len(data)):
                self.gps[int(data['time'][i])] = [float(data['lat'][i]), float(data['lon'][i])]


    # Scenario Control
    def scenario_load_from_dictionary(self):
        self.scenList.clear()
        self.scenario_cleanup()
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            self.scenList.addItem(f'{tmp[0]}, {tmp[2]}: {tmp[1]}')
        if 'additional_scenarios' not in self.main_dict.keys():
            self.main_dict['additional_scenarios'] = []          
    
    def scenario_app_open(self):
        if self.NOW == -1:
            return
        self.scenario_app = ScenarioApp(time_now=self.NOW,
                                         callback=self.scenario_insert_from_app,
                                         additional=self.main_dict['additional_scenarios'])
        self.scenario_app.show()

    def scenario_insert_from_app(self, time, scenario, add_scenario=None):
        if add_scenario is not None and add_scenario not in self.main_dict['additional_scenarios']:
            self.main_dict['additional_scenarios'].append(add_scenario)
        time_p = datetime.datetime.fromtimestamp(float(time)/1e9).strftime('%H:%M:%S.%f')[:-3]
        id = self.scenList.count() + 1
        self.main_dict['scenarios'][time] = (id, scenario, time_p)  # time, scenario
        self.scenario_cleanup()
        self.scenList.clear()
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            self.scenList.addItem(f'{tmp[0]}, {tmp[2]}: {tmp[1]}')

    def scenario_edit(self):
        id = self.scenList.currentRow()+1
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            if tmp[0] == id:
                self.scenario_app = ScenarioApp(time_now=key,
                                                scenario=tmp[1],
                                                callback=self.scenario_insert_from_app,
                                                additional=self.main_dict['additional_scenarios'])
                self.scenario_app.show()
    
    def scenario_remove(self):
        id = self.scenList.currentRow()+1
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            if tmp[0] == id:
                del self.main_dict['scenarios'][key]
                self.scenario_cleanup()
                self.scenList.clear()
                break
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            self.scenList.addItem(f'{tmp[0]}, {tmp[2]}: {tmp[1]}')


    def scenario_goto_callback(self):
        id = self.scenList.currentRow()+1
        for key in self.main_dict['scenarios'].keys():
            tmp = self.main_dict['scenarios'][key]
            if tmp[0] == id:
                self.ROStimeBox.setText(str(key))
                new_frame = get_closest(str(key), self.sync['rev'])[1]
                self.video_slider_moved_callback(int(new_frame))
                return

    def scenario_cleanup(self):
        tmp = self.main_dict['scenarios']
        self.main_dict['scenarios'] = {}
        time_list = list(tmp.keys())
        time_list.sort()
        for id, time in enumerate(time_list):
            self.main_dict['scenarios'][time] = (id+1, tmp[time][1], tmp[time][2])



    #### General  
    def main_refresh(self):
        if self.playing:
            self.video_play_callback()
        
        try:
            self.cap.release()
        except:
            pass
        self.timer.stop()
        self.cap = None
        self.total_frames = 0

        self.playBut.setEnabled(False)
        self.setIcon(self.playBut, 'play')
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

      
    def main_wallclock_update(self):
        try:
            self.NOW = int(self.ROStimeBox.toPlainText())
            self.DTBox.setText(str(datetime.datetime.fromtimestamp(float(self.NOW)/1e9)))
            self.bridge.map_current_position_callback(get_closest(self.NOW, self.gps)[1])
        except:
            self.NOW = -1

    def main_load_info(self):
        self.main_extract_info()
        for key in self.main_dict['info'].keys():
            description = self.main_dict['info'][key]
            self.infoL.addItem(f'{key}: {description}')

    def main_extract_info(self):
        if 'info' in self.main_dict.keys():
            return
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
        
    
    def load_all(self):
        self.video_camera_sync()
        self.map_generate_gps_dictionary()
        self.video_camera_select()
        self.video_load()
        self.map_load()
        self.main_load_info()
        self.scenario_load_from_dictionary()
        self.plot_load()

    def main_button_set_all(self, lock=False):
        self.scenAddB.setEnabled(lock)
        self.scenEditB.setEnabled(lock)
        self.scenRemoveB.setEnabled(lock)
        self.scenGoToB.setEnabled(lock)
        self.scenImportB.setEnabled(lock)
        
    def open_dads(self):
        self.main_refresh()
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
        self.load_all()
        self.main_button_set_all(True)

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

    
    # Extra Tools
    def add_on_open_dads_wizard(self):
        self.wizard_window = WizardApp()
        self.wizard_window.show()

    def add_on_open_bag_to_csv(self):
        self.to_csv_window = BagToCsvApp()
        self.to_csv_window.show()

    def add_on_open_video_edit(self):
        self.video_window = VideoApp()
        self.video_window.show()

    def add_on_open_about(self):
        self.about_window = aboutPage()
        self.about_window.show()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())