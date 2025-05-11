import sys
import cv2
import os
from PIL import Image
import numpy as np
import json
import pandas as pd

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QSlider, QFileDialog, QDialog, QStackedWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage


from pages.plot import Ui_plot

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

class PlotApp(QtWidgets.QWidget, Ui_plot):
    def __init__(self, main_dict: dict, extern=None):
        super(PlotApp, self).__init__()
        self.setAttribute(QtCore.Qt.WA_QuitOnClose)
        self.setupUi(self)
        self.main_dict = main_dict
        self.extern = extern
        self.adjustUI()

    def adjustUI(self):
        to_be_checked = []
        for plt in self.main_dict['plots']:
            to_be_checked.append((plt[1], plt[2]))
        for topic in self.main_dict['topics'].keys():
            self.colList.addItem('--' + topic)
            data = pd.read_csv(os.path.join(self.main_dict['pwd'], 'csv', self.main_dict['topics'][topic][0]+'.'+topic))
            for col in data.columns:
                if col == 'time':
                    continue
                self.add_item(col)
                if 'plots' not in self.main_dict:
                    self.main_dict['plots'] = []
                if (topic, col) in to_be_checked:
                    self.colList.item(self.colList.count() - 1).setCheckState(Qt.Checked)
 
        self.doneB.clicked.connect(self.get_checked_items)

    def add_item(self, text):
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.colList.addItem(item)

    def get_checked_items(self):
        checked = []
        topic = ""
        idx = 0
        for i in range(self.colList.count()):
            item = self.colList.item(i)
            if item.text().startswith('--'):
                topic = item.text()[2:]
                continue
            if item.checkState() == Qt.Checked:
                checked.append((idx, topic, item.text()))
                idx += 1
        self.main_dict['plots'] = checked
        self.extern(self.main_dict)
        self.close()
