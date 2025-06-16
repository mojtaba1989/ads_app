import sys
if sys.version_info < (3, 10):
    raise Exception("Python 3.10 or newer required")
import os
import json
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
import pandas as pd
import datetime

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QSlider, QFileDialog, QDialog,
    QStackedWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QObject, pyqtSlot, QUrl

try:
    from pages.auto_scenario import Ui_Wiz_1
except:
    from auto_scenario import Ui_Wiz_1

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)
dir_path = os.path.dirname(dir_path)

class AutoscenarioApp(QtWidgets.QWidget, Ui_Wiz_1):
    def __init__(self, main_dict, parent=None, external_1=None, external_2=None):
        super(AutoscenarioApp, self).__init__(parent)
        self.setupUi(self)
        self.dict = main_dict
        self.external_1 = external_1
        self.external_2 = external_2
        self.adjustUI()

    def adjustUI(self):
        self.detectB.clicked.connect(self.run)
        self.scen_list.itemClicked.connect(self.handle_item_click)
        self.exportB.clicked.connect(self.export)

    def data_prep(self):
        self.ssc_velocity = pd.DataFrame()
        for csv_file in self.dict['topics']['ssc_velocity']:
            csv_file = os.path.join(self.dict['pwd'], 'csv', csv_file + '.' + "ssc_velocity")
            self.ssc_velocity = pd.concat((self.ssc_velocity, pd.read_csv(csv_file, index_col=None)))
        
        self.steering_feedback = pd.DataFrame()
        for csv_file in self.dict['topics']['steering_feedback']:
            csv_file = os.path.join(self.dict['pwd'], 'csv', csv_file + '.' + "steering_feedback")
            self.steering_feedback = pd.concat((self.steering_feedback, pd.read_csv(csv_file, index_col=None)))
        

        self.ssc_velocity = self.ssc_velocity.sort_values('time')
        self.steering_feedback = self.steering_feedback.sort_values('time')

    def filter_rapid_events(self, df, min_gap_secs=5.0):
        df = df.sort_values('time')
        df['time_diff'] = df['time'].diff() / 1e9
        return df[df['time_diff'] > min_gap_secs].drop(columns='time_diff')

    def collapse_similar_events(self, events_df, time_gap_secs=60):
        events_df = events_df.sort_values('time').reset_index(drop=True)
        collapsed = []
        prev_event = None
        for idx, row in events_df.iterrows():
            if prev_event is None:
                collapsed.append(row)
                prev_event = row
            else:
                same_type = row['event'] == prev_event['event']
                close_in_time = (row['time'] - prev_event['time']) <= (time_gap_secs * 1e9)
                if not (same_type and close_in_time):
                    collapsed.append(row)
                    prev_event = row
        return pd.DataFrame(collapsed)
    
    def detect_events(self):
        self.ssc_velocity['accel_diff'] = self.ssc_velocity['acceleration'].diff()


        # Lane Changes and Turns (merge steering and velocity)
        merged = pd.merge_asof(
            self.steering_feedback[['time', 'steering']].sort_values('time'),
            self.ssc_velocity[['time', 'velocity']].sort_values('time'),
            on='time')
        
        
        turns = merged[(merged['velocity'] < 10) & (merged['steering'].abs() > 2.0)]
        turns = self.filter_rapid_events(turns, min_gap_secs=10)
        turns['event'] = 'Turn'

        lane_change1 = merged[(merged['steering'].abs() > 0.6) & (merged['steering'].abs() < 1.5)]
        exclusion_window_ns = 7 * 1e9
        for t in turns['time']:
            lane_change1 = lane_change1[~((lane_change1['time'] >= t - exclusion_window_ns) &
           (lane_change1['time'] <= t + exclusion_window_ns))]
        lane_change = self.filter_rapid_events(lane_change1, min_gap_secs=6)
        lane_change['event'] = 'Lane Change'

        events = pd.concat([lane_change[['time', 'event']],turns[['time', 'event']]])

        events = self.collapse_similar_events(events, time_gap_secs=60)
        events = events.sort_values('time').reset_index(drop=True)
        return events[['time', 'event']].dropna()
    
    def add_item(self, text):
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.scen_list.addItem(item)

    def handle_item_click(self, item):
        if item.text() == 'Select All':
            for i in range(self.scen_list.count()):
                self.scen_list.item(i).setCheckState(Qt.Checked)
            self.scen_list.item(1).setCheckState(Qt.Unchecked)
        elif item.text() == 'Deselect All':
            for i in range(self.scen_list.count()):
                self.scen_list.item(i).setCheckState(Qt.Unchecked)

    def get_checked_items(self):
        checked = []
        for i in range(2, self.scen_list.count()):
            item = self.scen_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(i)
        return checked
            
    def run(self):
        self.data_prep()
        self.events = self.detect_events()
        tmp = {}
        for r in range(self.events.shape[0]):
            tmp[int(self.events.iloc[r]['time'])] = [r, self.events.iloc[r]['event'], datetime.datetime.fromtimestamp(float(self.events.iloc[r]['time'])/1e9).strftime('%H:%M:%S.%f')[:-3]]
        self.add_item('Select All')
        self.add_item('Deselect All')
        for key in tmp.keys():
            self.add_item(f'{tmp[key][0]}, {tmp[key][2]}: {tmp[key][1]}')
        self.events = tmp
    

    def export(self):
        checked = self.get_checked_items()
        for idx in checked:
            tmp_id  = idx - 2
            for key in self.events.keys():
                if self.events[key][0] == tmp_id:
                    self.update_scen_list(key, self.events[key][1])

        self.close()

    def update_scen_list(self, time, scenario):
        self.external_1(str(time), scenario, scenario)
            
    

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    AutoScenarioApp = QtWidgets.QWidget()
    ui = Ui_Wiz_1()
    ui.setupUi(AutoScenarioApp)
    AutoScenarioApp.show()
    sys.exit(app.exec_())

