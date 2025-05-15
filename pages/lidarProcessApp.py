import sys
import os
import numpy as np
import json
import pandas as pd

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
     QFileDialog, QListWidgetItem
)
from PyQt5.QtCore import Qt
try:
    from pages.lidar_process import Ui_Form
except:
    from lidar_process import Ui_Form

def get_label(label: str):
    if 'car' in label:
        return 'car'
    elif 'pedestrian' in label:
        return 'pedestrian'
    elif 'bike' in label:
        return 'bike'
    else:
        return ''
    
def get_closest(key, dict):
        if dict=={}:
            return 0, 0
        try:
            return key, dict[key]
        except:
            key_n = min(dict.keys(), key=lambda x: abs(int(x) - int(key)))
            return key_n, dict[key_n]

class trackObj:
    def __init__(self, Q_var=1, R_var=1):
        self.id = None
        self.x = np.array([[0, 0, 0, 0]]).transpose()
        self.F = np.eye(4)
        self.H = np.eye(4)[:2,]
        self.Q = np.eye(4)*Q_var
        self.R = np.eye(2)*R_var
        self.P = np.eye(4)
        self.K = np.eye(4)
        self.category = None
        self.history = []
        self.active = False
        self.matched = False

    def init_filter(self, z, time):
        z = z.transpose().tolist()[0]
        self.x = np.array([[z[0], z[1], 0, 0]]).transpose()
        self.history.append((time, self.x, 0))

    def update(self, time, z = None, x_v_dot=0,d_theta=0):
        dT = (time - self.history[-1][0])*1e-9
        self.F[0,2] = dT
        self.F[1,3] = dT

        d_theta = np.deg2rad(d_theta)
        Rot = np.array([[np.cos(d_theta), -np.sin(d_theta), 0, 0], [np.sin(d_theta), np.cos(d_theta), 0, 0], [0, 0, np.cos(d_theta), -np.sin(d_theta)], [0, 0, np.sin(d_theta), np.cos(d_theta)]])

        x_hat = np.dot(self.F, self.x)
        x_hat = np.dot(Rot, x_hat)
        x_hat = x_hat - np.array([[-x_v_dot*dT, 0, 0, 0]]).transpose()

        P_hat = np.dot(np.dot(self.F, self.P), self.F.transpose()) + self.Q

        self.K = np.dot(np.dot(P_hat, self.H.transpose()), np.linalg.inv(np.dot(np.dot(self.H, P_hat), self.H.transpose()) + self.R))
        self.x = x_hat
        if z is not None:
            self.x += np.dot(self.K, (z - np.dot(self.H, x_hat)))
        self.P = np.dot(np.eye(4) - np.dot(self.K, self.H), P_hat)
        self.history.append((time, self.x, self.get_yaw()))
        self.matched = True
    
    def get_yaw(self):
        # return np.degrees(np.arctan2(self.x[3], self.x[2]).item())
        x = [i[1][0].item() for i in self.history]
        y = [i[1][1].item() for i in self.history]
        diff_x = np.diff(x).mean()
        diff_y = np.diff(y).mean()
        return np.degrees(np.arctan2(diff_y, diff_x))
    
    def projected_dist(self, z, time):
        dT = (time - self.history[-1][0])*1e-9
        F = np.array([[1, 0, dT, 0], [0, 1, 0, dT], [0, 0, 1, 0], [0, 0, 0, 1]])
        xhat = np.dot(F, self.x)[:2,]
        return np.linalg.norm(xhat - z)
    
    def obj_dist(self, obj, time):
        return self.projected_dist(obj.z, time)
    
class newObj:
    def __init__(self, x, y, cat):
        self.z = np.array([[x, y]]).transpose()
        self.category = get_label(cat)

class newObjList:
    def __init__(self):
        self.newObjList = []
        self.time = None
    
    def add(self, x, y, time, category):
        self.newObjList.append(newObj(x, y, category))
    
    def remove_FP(self, xlim=3, ylim=2):
        self.newObjList = [obj for obj in self.newObjList if not(abs(obj.z[0]) <= xlim and abs(obj.z[1]) <= ylim)]
    
    def dist(obj_registered, obj_new, time):
        return obj_registered.projected_dist(obj_new.z, time)

class lidarProcessApp(QtWidgets.QWidget, Ui_Form):
    def __init__(self, extern=None):
        super(lidarProcessApp, self).__init__()
        self.setupUi(self)
        self.extern = extern
        self.adjustUI()
        self.speed = None
        self.heading = None

    def adjustUI(self):
        self.browseB.clicked.connect(self.open_dads)
        self.csvList.itemClicked.connect(self.handle_item_click)
        self.applyB.clicked.connect(self.cleanUp)

        self.progressBar.setValue(0)
        self.progressBar.setEnabled(False)
        self.report.setText('')

    def add_item(self, text):
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.csvList.addItem(item)
            

    def open_dads(self):
        self.main_dict = {}
        self.csvList.clear()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open DADS File', filter='Trip Files (*.DADS)'
        )
        self.dads_pwd.clear()
        self.dads_pwd.addItem(file_path)
        try:
            with open(file_path, 'r') as f:
                self.main_dict = json.load(f)
        except:
            self.main_dict = {}
            return
        self.add_item('Select All')
        self.add_item('Deselect All')
        for file in self.main_dict['topics']['lidarObj']:
            self.add_item(file)

    def handle_item_click(self, item):
        if item.text() == 'Select All':
            for i in range(self.csvList.count()):
                self.csvList.item(i).setCheckState(Qt.Checked)
        elif item.text() == 'Deselect All':
            for i in range(self.csvList.count()):
                self.csvList.item(i).setCheckState(Qt.Unchecked)

    def get_checked_items(self):
        checked = []
        for i in range(2, self.csvList.count()):
            item = self.csvList.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked
    
    def load_extra(self):
        checked = self.get_checked_items()
        if not checked:
            return
        dir_name = os.path.dirname(self.dads_pwd.item(0).text())
        self.speed = {}
        for file in checked:
            file_path = os.path.join(dir_name, 'csv', file + '.ssc_velocity')
            data = pd.read_csv(file_path)
            data = data.dropna()
            data = data.reset_index(drop=True)
            for i in range(len(data)):
                self.speed[int(data.loc[i, 'time'])] = float(data.loc[i, 'velocity'])
        self.heading = {}
        for file in checked:
            file_path = os.path.join(dir_name, 'csv', file + '.steering_feedback')
            data = pd.read_csv(file_path)
            data = data.dropna()
            data = data.reset_index(drop=True)
            for i in range(len(data)):
                self.speed[int(data.loc[i, 'time'])] = -float(data.loc[i, 'steering'])

    
    def cleanUp(self):
        self.report.setText('Task 1/3: Cleaning CSV files...')
        checked = self.get_checked_items()
        if not checked:
            return
        dir_name = os.path.dirname(self.dads_pwd.item(0).text())
        file_name = os.path.join(checked[0]+'.lidar')
        self.progressBar.setMaximum(len(checked))
        self.progressBar.setEnabled(True)
        self.progressBar.setValue(0)
        data_list = []
        idx = 0
        max = 0
        for file in checked:
            idx += 1
            self.progressBar.setValue(idx)
            file_path = os.path.join(dir_name, 'csv', file + '.lidarObj')
            data = pd.read_csv(file_path)
            data = data.dropna()
            data = data.reset_index(drop=True)
            data_list.append(data)
            max += len(data)
        self.report.setText('Task 2/3: Merging CSV files...')
        self.progressBar.setMaximum(max)
        self.progressBar.setValue(0)
        self.lidar = {}
        idx = 0
        for data in data_list:
            for i in range(len(data)):
                idx += 1
                self.progressBar.setValue(idx)
                label = str(data['label'][i])
                if 'car' in label:
                    label = 'car'
                elif 'bike' in label:
                    label = 'truck'
                elif 'pedestrian' in label:
                    label = 'pedestrian'
                else:
                    continue
                entry = (data.loc[i, 'x'], data.loc[i, 'y'], data.loc[i, 'z'], label)
                key = int(data.loc[i, 'time'])
                if data.loc[i, 'time'] not in self.lidar.keys():
                    self.lidar[key] = [entry]
                else:
                    self.lidar[key].append(entry)
        self.report.setText('Task 3/3: Saving as json...')
        with open(os.path.join(dir_name, file_name), 'w') as f:
            json.dump(self.lidar, f)
        self.main_dict['lidar'] = file_name
        self.extern_func()
        self.report.setText('Done!')

    def cleanUp_with_Kalman(self):
        self.load_extra()
        self.report.setText('Task 1/3: Cleaning CSV files...')
        checked = self.get_checked_items()
        if not checked:
            return
        dir_name = os.path.dirname(self.dads_pwd.item(0).text())
        file_name = os.path.join(checked[0]+'.lidar')
        self.progressBar.setMaximum(len(checked))
        self.progressBar.setEnabled(True)
        self.progressBar.setValue(0)
        idx = 0
        lidar_data = pd.DataFrame()
        for file in checked:
            idx += 1
            self.progressBar.setValue(idx)
            file_path = os.path.join(dir_name, 'csv', file + '.lidarObj')
            data = pd.read_csv(file_path)
            data = data.dropna()
            lidar_data = pd.concat([lidar_data, data], axis=0)
        
        lidar_data = lidar_data.reset_index(drop=True)
        time = np.unique(lidar_data['time'])
        self.report.setText('Task 2/3: Tracking with KF...')
        self.progressBar.setMaximum(len(time))
        self.progressBar.setValue(0)
        tracking = []
        archived = []
        id_ = 0
        progress_idx = 0
        for t in time:
            _, speed_ = get_closest(t, self.speed)
            _, heading_ = get_closest(t, self.heading)

            progress_idx += 1
            self.progressBar.setValue(progress_idx)
            for obj in tracking:
                obj.matched = False
                if t - obj.history[-1][0] > 1*1e9:
                    obj.active = False
            df = lidar_data[lidar_data['time'] == t]
            df = df.reset_index(drop=True)
            new = newObjList()
            for i in range(len(df)):
                new.add(df.loc[i, 'x'], df.loc[i, 'y'], df.loc[i, 'time'], df.loc[i, 'label'])
            new.remove_FP(xlim=2.5, ylim=1)
            for nobj in new.newObjList:
                dist = np.array([obj.obj_dist(nobj, t) for obj in tracking if obj.active and not obj.matched])
                dist_id = np.array([obj.id for obj in tracking if obj.active and not obj.matched])
                if dist.size==0 or dist.min() >= 2:
                    tracking.append(trackObj())
                    tracking[-1].id = id_
                    tracking[-1].init_filter(nobj.z, t)
                    tracking[-1].active = True
                    tracking[-1].matched = True
                    tracking[-1].category = nobj.category
                    id_ += 1
                else:
                    for idx , obj in enumerate(tracking):
                        if obj.id == dist_id[np.argmin(dist)]:
                            id_target = idx
                            break

                    tracking[id_target].update(t, nobj.z, speed_, heading_)
                    tracking[id_target].matched = True
            for obj in tracking:
                if not obj.active:
                    archived.append(obj)
                    tracking.remove(obj)
        for obj in tracking:
            archived.append(obj)
        self.report.setText('Task 3/3: Saving as json...')
        with open('tmp.csv', 'w') as f:
            f.write('time,id,x,y,label,yaw\n')
            for idx, obj in enumerate(archived):
                for h in obj.history:
                    f.write(f'{int(h[0])},{obj.id},{h[1][0].item()},{h[1][1].item()},{obj.category},{h[2]}\n')
        data = pd.read_csv('tmp.csv')
        data = data.sort_values(['time', 'id'])
        self.report.setText('Task 3/3: Converting to json...')
        self.progressBar.setMaximum(len(data))
        self.progressBar.setValue(0)
        self.lidar = {}
        idx = 0
        for i in range(len(data)):
            idx += 1
            self.progressBar.setValue(idx)
            label = str(data.loc[i, 'label'])
            entry = (data.loc[i, 'x'], data.loc[i, 'y'], data.loc[i, 'yaw'], label)
            key = int(data.loc[i, 'time'])
            if data.loc[i, 'time'] not in self.lidar.keys():
                self.lidar[key] = [entry]
            else:
                self.lidar[key].append(entry)
        
        with open(os.path.join(dir_name, file_name), 'w') as f:
            json.dump(self.lidar, f)
        self.main_dict['lidar'] = file_name
        self.extern_func()
        os.remove('tmp.csv')
        self.report.setText('Done!')
        

        return

    def extern_func(self):
        if self.extern is None:
            return
        self.extern(self.main_dict)

                        

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = lidarProcessApp()
    window.show()
    sys.exit(app.exec_())