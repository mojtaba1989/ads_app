try:
    from pages.here_api import Ui_Form
except:
    from here_api import Ui_Form


from geopy.distance import geodesic
import pandas as pd
import os
import numpy as np
import folium
import time
import sys
import requests
import json
import flexpolyline as fp

from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import (QTimer, QObject, QUrl, pyqtSlot)
from PyQt5.QtWebChannel import QWebChannel

from PyQt5 import QtCore, QtGui, QtWidgets


from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem
)

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)
parent_path = os.path.dirname(dir_path)


def get_min_of_max(lst, target):
    for idx, value in enumerate(lst):
        if value >= target:
            return idx, value
    return None, None
    


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

    @pyqtSlot(list)
    def sendRoute(self, route):
        pass

    @pyqtSlot(float, float, str)
    def add_marker(self, pose, msg):
        js = f"add_marker({pose[0]}, {pose[1]}, '{json.dumps(msg)}');"
        self.webview.page().runJavaScript(js)



class HereApiApp(QtWidgets.QWidget, Ui_Form):
    def __init__(self, main_dict, gps_dict, external=None, api_key='uUFZJMYlitfRsDjEJIHqZ1fWoc6jhycasfFwsIBlhWs'):
        super(HereApiApp, self).__init__()
        self.main_dict = main_dict
        self.gps = gps_dict
        self.setAttribute(QtCore.Qt.WA_QuitOnClose)
        self.setupUi(self)
        self.adjustUI()
        self.total_distance = 0
        self.api_key = api_key
        self.external = external
        self.routing_url = "https://router.hereapi.com/v8/routes"
        self.report('Loading map ...')
        self.progressBar.setValue(0)
        self.progressBar.setEnabled(False)
        self.exportBut.setEnabled(False)
        self.runBut.setEnabled(False)


    def adjustUI(self):
        QTimer.singleShot(0, self.initWebEngine)
        self.seg_num.setMinimum(1)
        self.runBut.clicked.connect(self.run)
        self.refreshButton.clicked.connect(self.load_map)
        self.seg_num.valueChanged.connect(self.seg_changed)
        self.exportBut.clicked.connect(self.export)

    def run_external(self):
        self.external()


    def initWebEngine(self):
        if hasattr(self, 'mapView') and self.mapView is not None:
            self.verticalLayout.removeWidget(self.mapView)
            self.mapView.setParent(None)
            self.mapView.deleteLater()  # Optional: to free memory
            self.mapView = None
        self.mapView = QWebEngineView(self.groupBox)
        self.mapView.setObjectName("mapView")
        self.verticalLayout.addWidget(self.mapView)
        QTimer.singleShot(2000, self.load_map)

    def report(self, msg, max_value=None):
        self.status_txt.setText(msg)
        if not max_value is None:
            self.reset_progress_bar(max_value)


    def reset_progress_bar(self, max_value=100):
        self.progressBar.setEnabled(True)
        self.progressBar.setValue(0)
        self.progressBar.setMaximum(max_value)


    def init_route_dict(self):
        self.route = {'points':[],
                      'actions':[],
                      'speed_limits':[]
                      }


    def get_dist(self):
        self.total_distance = 0
        self.ros_time = [key for key in self.gps.keys()]
        self.ros_time.sort()
        self.distance = []
        self.report('Loading GPS points', len(self.ros_time))
        for i, key in enumerate(self.ros_time):
            self.progressBar.setValue(i)
            if i == 0:
                self.distance.append(self.total_distance)
                continue
            Pfrom = tuple(self.gps[self.ros_time[i-1]])
            Pto = tuple(self.gps[self.ros_time[i]])
            self.total_distance += geodesic(Pfrom, Pto).m
            self.distance.append(self.total_distance)
        self.progressBar.setValue(i+1)
        return True
        

    def get_point_list(self):
        if self.total_distance == 0:
            return
        segment_dist = np.linspace(0, self.total_distance, self.seg_num.value()+1)[1:-1]
        self.point_time_list = [self.ros_time[0]]
        self.report('Segmenting route', len(segment_dist))
        for i, target in enumerate(segment_dist):
            self.progressBar.setValue(i)
            idx, _ = get_min_of_max(self.distance, target)
            if idx is None:
                return False
            self.point_time_list.append(self.ros_time[idx])
        self.point_time_list.append(self.ros_time[-1])
        self.progressBar.setValue(i+1)
        return True
    

    def get_responses(self):
        self.report('Get routes from HERE API', len(self.point_time_list))
        self.response_list = []
        for i in range(1, len(self.point_time_list)):
            self.progressBar.setValue(i)
            res = self.request(self.point_time_list[i-1], self.point_time_list[i])
            if res is not None: 
                self.response_list.append(res)
                # with open(f"{i}.json", 'w') as f:
                #     json.dump(res, f, indent=4) 
        self.progressBar.setValue(i+1)
        return
    

    def read_responses(self):
        self.report('Analyzing HERE API response', len(self.response_list))
        last_speed = -1
        for i, route in enumerate(self.response_list):
            self.progressBar.setValue(i)
            points = route['routes'][0]['sections'][0]['polyline']
            points = fp.decode(points)
            for p in points:
                if not p in self.route['points']:
                    self.route['points'].append(p)
            for action in route['routes'][0]['sections'][0]['actions']:
                if not action['action'] in ['depart', 'arrive']:
                    tmp = {'action': action['action'],
                           'location': points[action['offset']]}
                    self.route['actions'].append(tmp)
            for spl in route['routes'][0]['sections'][0]['spans']:
                speed = int(np.ceil(spl['speedLimit']*2.23694))
                if speed != last_speed:
                    last_speed = speed 
                    tmp = {'speed_limit': speed,
                           'location': points[spl['offset']]}
                    self.route['speed_limits'].append(tmp)
        self.progressBar.setValue(i+1)


    def update_map(self):
        self.report('Updating Map ...')
        to_show = []
        if self.route['points']:
            for action in self.route['actions']:
                tmp = (action['location'], [f"action: {action['action']}"])
                to_show.append(tmp)
            for sp in self.route['speed_limits']:
                try:
                    idx = [i[0] for i in to_show].index(sp['location'])
                    to_show[idx][1].append(f"speed limit change: {sp['speed_limit']}")
                except ValueError:
                    to_show.append((sp['location'], [f"speed limit change: {sp['speed_limit']}"]))
            for p in to_show:
                self.bridge.add_marker(p[0], ' and '.join(p[1]))
                    


    def seg_changed(self):
        self.runBut.setEnabled(True)


    def request(self, start, end):
        start = self.gps[start]
        end = self.gps[end]
        params = {
                'apikey': self.api_key,
                'transportMode': 'car',
                'origin': f"{start[0]:.6f},{start[1]:.6f}",
                'destination': f"{end[0]:.6f},{end[1]:.6f}",
                'return': 'polyline,summary,actions,instructions',
                'spans': 'speedLimit,dynamicSpeedInfo'
            }
        response = requests.get(self.routing_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None


    def load_map(self):
        file_path = os.path.abspath(os.path.join(parent_path, "map.html"))
        self.mapView.setUrl(QtCore.QUrl.fromLocalFile(file_path))

        self.channel = QWebChannel()
        self.bridge = Bridge(self.mapView)
        self.channel.registerObject('bridge', self.bridge)
        self.mapView.page().setWebChannel(self.channel)

        route = [[lat, lon] for lat, lon in self.gps.values()]
        js_array = str(route).replace("'", "")  # Simple conversion to JS array format

        js = f"setRoute({js_array});"
        QTimer.singleShot(2000, lambda: self.mapView.page().runJavaScript(js))
        self.report('Map loaded')
        QTimer.singleShot(2000, lambda: self.runBut.setEnabled(True))


    def run(self):
        self.init_route_dict()
        self.get_dist()
        self.get_point_list()
        self.get_responses()
        self.read_responses()
        self.update_map()
        self.report('Done!')
        self.progressBar.setEnabled(False)
        self.exportBut.setEnabled(True)
        self.runBut.setEnabled(False)

    def export(self):
        tmp = self.route
        del tmp['points']
        self.main_dict['HereAPI'] = tmp
        self.run_external()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HereApiApp(None, None)
    window.show()
    sys.exit(app.exec_())
    
