import os
import pandas as pd
import numpy as np
import json
from PyQt5 import QtWidgets

class TTCPlotApp(QtWidgets.QWidget):
    def __init__(self, main_dict, plot_callback):
        super().__init__()
        self.setWindowTitle("TTC Plot Viewer")
        self.resize(300, 100)
        self.main_dict = main_dict
        self.plot_callback = plot_callback

        layout = QtWidgets.QVBoxLayout(self)
        load_btn = QtWidgets.QPushButton("Load TTC Plot")
        load_btn.clicked.connect(self.load_ttc_plot)
        layout.addWidget(load_btn)

    def load_ttc_plot(self):
        
        base_path = os.path.join(self.main_dict['pwd'], 'csv')
        velocity_file = os.path.join(base_path, self.main_dict['topics']['ssc_velocity'][0] + ".ssc_velocity")
        position_file = os.path.join(base_path, self.main_dict['topics']['pos'][0] + ".pos")
        heading_file = os.path.join(base_path, self.main_dict['topics']['heading'][0] + ".heading")
        lidar_file = os.path.join(self.main_dict['pwd'], self.main_dict['lidar'])
        
        velocity_df = pd.read_csv(velocity_file)
        position_df = pd.read_csv(position_file)
        heading_df = pd.read_csv(heading_file)
        
        velocity_df['time'] = velocity_df['time'].astype(np.int64)
        position_df['time'] = position_df['time'].astype(np.int64)
        heading_df['time'] = heading_df['time'].astype(np.int64)
        
        # Merge ego data
        ego_df = pd.merge_asof(pd.merge_asof(
            velocity_df.sort_values('time'),
            position_df.sort_values('time'),on='time',
            direction='nearest',
            tolerance=np.int64(5e7)),
        heading_df.sort_values('time'),on='time',direction='nearest',tolerance=np.int64(5e7))
        ego_df = ego_df.dropna(subset=['velocity', 'lat', 'lon', 'heading'])
        
        ego_df['heading_rad'] = np.deg2rad(ego_df['heading'])
        ego_df['heading_x'] = np.cos(ego_df['heading_rad'])
        ego_df['heading_y'] = np.sin(ego_df['heading_rad'])
        
        with open(lidar_file, 'r') as f:
            lidar_data = json.load(f)
            lidar_data = {int(k): v for k, v in lidar_data.items()}
            lidar_keys = sorted(lidar_data.keys())

        def find_closest_lidar_timestamp(ts, keys, tolerance_ns=5e7):
            i = np.searchsorted(keys, ts)
            if i == 0:
                return keys[0] if abs(keys[0] - ts) <= tolerance_ns else None
            if i == len(keys):
                return keys[-1] if abs(keys[-1] - ts) <= tolerance_ns else None
            before, after = keys[i - 1], keys[i]
            return before if abs(before - ts) <= abs(after - ts) else after

        # Compute TTC
        ttc_records = []
        for _, row in ego_df.iterrows():
            ts = int(row['time'])
            ego_vel = row['velocity']
            if pd.isna(ego_vel) or float(ego_vel) < 0.2:
                continue
            ego_vel = float(ego_vel)
            heading_vec = np.array([row['heading_x'], row['heading_y']])
            closest_ts = find_closest_lidar_timestamp(ts, lidar_keys)
            if closest_ts is None: 
                continue
        
            detections = lidar_data[closest_ts]
            min_ttc = np.inf
            for obj in detections:
                obj_x, obj_y, _, label = obj
                rel_vec = np.array([obj_x, obj_y])
                dist_along_path = np.dot(rel_vec, heading_vec)
                lateral_offset = np.linalg.norm(rel_vec - dist_along_path * heading_vec)
                if dist_along_path < 5 or lateral_offset > 1.5:
                    continue
                if label not in ['car', 'truck', 'bus', 'pedestrian']:
                    continue
                ttc = dist_along_path / ego_vel
                if ttc < min_ttc:
                    min_ttc = ttc
            if min_ttc < np.inf:
                ttc_records.append((closest_ts, min_ttc))
                        
        if not ttc_records:
            QtWidgets.QMessageBox.warning(self, "No TTCs", "No TTC values found.")
            return
                        
        ttc_records.sort()
        x = [rec[0] for rec in ttc_records]
        y = [rec[1] for rec in ttc_records]

        self.plot_callback(x, y, legend="TTC (s)")
        self.close()

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = TTCPlotApp({}, lambda x, y, legend: print(f"Plotting TTC with {len(x)} points"))
    window.show()
    sys.exit(app.exec_())

