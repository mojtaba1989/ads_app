import sys
import cv2
import os
from PIL import Image
import numpy as np
import json

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage

from pages.scenario import Ui_addScenario

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

class ScenarioApp(QtWidgets.QWidget, Ui_addScenario):
    def __init__(self, time_now, scenario=None, callback=None, parent=None, additional=[]):
        super(ScenarioApp, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_QuitOnClose)
        self.callback = callback
        self.time_now = time_now
        self.additional = additional
        self.Ex_scenario = scenario
        self.setupUi(self)
        self.adjustUI()
        

    def adjustUI(self):
        self.addB.clicked.connect(self.add_)
        self.load_scenarios()
        self.get_time()

    def load_scenarios(self):
        JSON_FILE = os.path.join(dir_path, 'scenario.json')
        with open(JSON_FILE, 'r') as f:
            self.ref = json.load(f)

        self.scenario.clear()
        for scenario in self.additional:
            self.scenario.addItem(scenario)
        separator_index = len(self.additional)
        self.scenario.addItem('-'*20)
        self.scenario.model().item(separator_index).setFlags(Qt.NoItemFlags)
        for scenario in self.ref['reference_scenarios']:
            self.scenario.addItem(scenario)
        if self.Ex_scenario != None:
            self.scenario.setCurrentText(self.Ex_scenario)

    def get_time(self):
        self.time.setPlainText(str(self.time_now))

    def add_(self):
        if self.customScen.toPlainText() == '':
            self.callback(self.time.toPlainText(), self.scenario.currentText())
        elif self.customScen.toPlainText() in self.ref['reference_scenarios']:
            self.callback(self.time.toPlainText(), self.scenario.currentText())
        elif self.customScen.toPlainText() in self.additional:
            self.callback(self.time.toPlainText(), self.scenario.currentText())
        else:
            self.callback(self.time.toPlainText(), self.customScen.toPlainText(), self.customScen.toPlainText())
        self.close()

