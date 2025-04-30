import sys
import cv2
import os
from PIL import Image
import numpy as np
import pandas as pd
import folium
from scipy.signal import decimate
import json


from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QSlider, QFileDialog, QDialog, QStackedWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage


from pages.wizard1 import Ui_Wiz_1
from pages.wizard2 import Ui_Wiz_2
from pages.wizard3 import Ui_Wiz_3
from pages.wizard4 import Ui_Wiz_4

from pages.videoProcessApp import VideoApp

class Page1(QtWidgets.QWidget, Ui_Wiz_1):
    def __init__(self, stacked_widget):
        super(Page1, self).__init__()
        self.setupUi(self)
        self.stacked_widget = stacked_widget
        

    def init_ui(self):
        self.addB.clicked.connect(self.add_)
        self.removeB.clicked.connect(self.remove_)
        self.moveUpB.clicked.connect(self.up_)
        self.moveDownB.clicked.connect(self.down_)
        self.nextB.clicked.connect(self.next_)
        self.sortB.clicked.connect(self.sort_)
    
    def add_(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileNames(caption="Open Rosbag File(s)", filter="Rosbag Files (*.bag)")
        if file_path == "":
            return
        for file in file_path:
            self.baglist.addItem(file)
    
    def remove_(self):
        for item in self.baglist.selectedItems():
            self.baglist.takeItem(self.baglist.row(item))

    def up_(self):
        current_row = self.baglist.currentRow()
        if current_row > 0:
            current_item = self.baglist.takeItem(current_row)
            self.baglist.insertItem(current_row - 1, current_item)
            self.baglist.setCurrentRow(current_row - 1)

    def down_(self):
        current_row = self.baglist.currentRow()
        if current_row < self.baglist.count() - 1:
            current_item = self.baglist.takeItem(current_row)
            self.baglist.insertItem(current_row + 1, current_item)
            self.baglist.setCurrentRow(current_row + 1)

    def next_(self):
        self.gen_dict()
        self.stacked_widget.widget(1).get_dict(self.main_dict)
        self.stacked_widget.setCurrentIndex(1)

    def sort_(self):
        items = [self.baglist.item(i).text() for i in range(self.baglist.count())]
        items.sort()
        self.baglist.clear()
        for item in items:
            self.baglist.addItem(item)
        
    def gen_dict(self):
        if self.baglist.count() == 0:
            return
        self.main_dict = {}
        self.main_dict['pwd'] = os.path.dirname(self.baglist.item(0).text())+'/'
        self.main_dict['bags'] = [self.baglist.item(i).text().replace(self.main_dict['pwd'], '') for i in range(self.baglist.count())]


class Page2(QtWidgets.QWidget, Ui_Wiz_2):
    def __init__(self, stacked_widget):
        super(Page2, self).__init__()
        self.setupUi(self)
        self.stacked_widget = stacked_widget

    def init_ui(self):
        self.previousB.clicked.connect(self.go_back)
        self.topiclist.itemClicked.connect(self.handle_item_click)
        self.nextB.clicked.connect(self.go_next)
        
    
    def go_back(self):
        self.stacked_widget.setCurrentIndex(0)

    def go_next(self):
        self.update_dict()
        self.stacked_widget.widget(2).get_dict(self.main_dict)
        self.stacked_widget.setCurrentIndex(2)

    def add_item(self, text):
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.topiclist.addItem(item)

    def updateList(self):
        self.topiclist.clear()
        self.add_item('Select All')
        self.add_item('Deselect All')
        topics = []
        for key in self.bag_dict.keys():
            for topic in self.bag_dict[key]['topics']:
                topics.append(topic)
        topics = np.unique(topics)
        for topic in topics:
            self.add_item(topic)

    def handle_item_click(self, item):
        if item.text() == 'Select All':
            for i in range(self.topiclist.count()):
                self.topiclist.item(i).setCheckState(Qt.Checked)
        elif item.text() == 'Deselect All':
            for i in range(self.topiclist.count()):
                self.topiclist.item(i).setCheckState(Qt.Unchecked)
        elif item.text().startswith('+++'):
            index = self.topiclist.row(item)
            for i in range(index + 1, self.topiclist.count()):
                if self.topiclist.item(i).text().startswith('    '):
                    self.topiclist.item(i).setCheckState(Qt.Checked)
                else:
                    break
    def get_checked_items(self):
        checked = []
        for i in range(2, self.topiclist.count()):
            item = self.topiclist.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked
    
    def get_dict(self, dict):
        self.main_dict = dict
        tmp = {}
        csv_list = os.listdir(os.path.join(self.main_dict['pwd'], 'csv'))
        for bag in self.main_dict['bags']:
            tmp[os.path.basename(bag)] = {'dir': os.path.join(self.main_dict['pwd'], 'csv'), 'topics': []}
            for csv in csv_list:
                if csv.startswith(os.path.basename(bag)):
                    tmp[os.path.basename(bag)]['topics'].append(csv.split('.')[-1])
        self.bag_dict = tmp
        self.updateList()
    
    def update_dict(self):
        final_topics = self.get_checked_items()
        tmp={}
        for topic in final_topics:
            tmp[topic] = []
            for key in self.bag_dict.keys():
                if topic in self.bag_dict[key]['topics']:
                    tmp[topic].append(key)
        self.main_dict['topics'] = tmp


class Page3(QtWidgets.QWidget, Ui_Wiz_3):
    def __init__(self, stacked_widget):
        super(Page3, self).__init__()
        self.setupUi(self)
        self.stacked_widget = stacked_widget
        self.main_dict = None

    def init_ui(self):
        self.previousB.clicked.connect(self.go_back)
        self.nextB.clicked.connect(self.go_next)
        self.processB.clicked.connect(self.openProcess)
        self.addB.clicked.connect(self.add_)
        self.removeB.clicked.connect(self.remove_)

    def go_back(self):
        self.stacked_widget.setCurrentIndex(1)

    def go_next(self):
        self.update_dict()
        self.stacked_widget.widget(3).get_dict(self.main_dict)
        self.stacked_widget.setCurrentIndex(3)

    def openProcess(self):
        self.process_window = VideoApp()
        self.process_window.show()

    def add_(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileNames(caption="Open Video File", filter="Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_path == "":
            return
        for file in file_path:
            self.videoList.addItem(file)
    
    def remove_(self):
        for item in self.videoList.selectedItems():
            self.videoList.takeItem(self.videoList.row(item))

    def get_dict(self, dict):
        self.main_dict = dict
    
    def update_dict(self):
        self.main_dict['video'] = []
        for i in range(self.videoList.count()):
            item = self.videoList.item(i).text().replace(self.main_dict['pwd'], '')
            self.main_dict['video'].append(item)

    
class Page4(QtWidgets.QWidget, Ui_Wiz_4):
    def __init__(self, stacked_widget):
        super(Page4, self).__init__()
        self.setupUi(self)
        self.stacked_widget = stacked_widget

    def init_ui(self):
        self.previousB.clicked.connect(self.go_back)
        self.finishB.clicked.connect(self.finish)
        self.gpsList.itemClicked.connect(self.handle_item_click)
        self.generateB.clicked.connect(self.gen_map)

    def go_back(self):
        self.stacked_widget.setCurrentIndex(2)

    def finish(self):
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save File",
            "",
            "DADS Files (*.DADS);;All Files (*)"
            )

        if file_path:
            if not file_path.endswith('.DADS'):
                file_path += '.DADS'
            with open(file_path, 'w') as f:
                json.dump(self.main_dict, f, indent=4)
            self.parent().close()


    def get_dict(self, dict):
        self.main_dict = dict
        self.add_Item('Select All')
        self.add_Item('Deselect All')
        for item in self.main_dict['topics']['gps']:
            self.add_Item(item)

    def add_Item(self, text):
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.gpsList.addItem(item)

    def handle_item_click(self, item):
        if item.text() == 'Select All':
            for i in range(self.gpsList.count()):
                self.gpsList.item(i).setCheckState(Qt.Checked)
        elif item.text() == 'Deselect All':
            for i in range(self.gpsList.count()):
                self.gpsList.item(i).setCheckState(Qt.Unchecked)

    def get_checked_items(self):
        checked = []
        for i in range(2, self.gpsList.count()):
            item = self.gpsList.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked
    
    def gen_map(self):
        gps_list = self.get_checked_items()
        points = []
        center = [0, 0]
        for f in gps_list:
            data = pd.read_csv(os.path.join(self.main_dict['pwd'], 'csv', f + '.pos'))
            for lat, lon in zip(data['lat'], data['lon']):
                points.append([lat, lon])
        lat = np.array([i[0] for i in points])
        lon = np.array([i[1] for i in points])
        center = [np.mean(lat), np.mean(lon)]
        map = folium.Map(location=center, zoom_start=12)
        for x, y in zip(lat, lon):
            folium.CircleMarker(location=[x, y],
                                radius=3,
                                color='red',
                                fill_color='red',
                                opacity=1).add_to(map)
        map.save(os.path.join(self.main_dict['pwd'], self.main_dict['bags'][0] + '.map.html'))
        self.webView.setUrl(QtCore.QUrl.fromLocalFile(os.path.join(self.main_dict['pwd'], 'map.html')))
        self.main_dict['map'] = self.main_dict['bags'][0] + '.map.html'


    

class WizardApp(QWidget):
    def __init__(self, parent=None):
        super(WizardApp, self).__init__()
        self.setWindowTitle("DADS Creator Wizard")
        self.resize(530, 350)
        layout = QVBoxLayout()
        self.stacked = QStackedWidget()
        self.page1 = Page1(self.stacked)
        self.page2 = Page2(self.stacked)
        self.page3 = Page3(self.stacked)
        self.page4 = Page4(self.stacked)

        self.page1.init_ui()
        self.page2.init_ui()
        self.page3.init_ui()
        self.page4.init_ui()


        self.stacked.addWidget(self.page1)
        self.stacked.addWidget(self.page2)
        self.stacked.addWidget(self.page3)
        self.stacked.addWidget(self.page4)

        layout.addWidget(self.stacked)
        self.setLayout(layout)
