import os
import json
import numpy as np
import pandas as pd
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

class TTC360App(QtWidgets.QWidget):
    def __init__(self, main_dict,from_saved=False):
        super().__init__()
        self.main_dict = main_dict
        self.setWindowTitle("TTC 360° Viewer")
        self.resize(600, 600)

        self.figure, self.ax = plt.subplots(subplot_kw={'projection': 'polar'})
        self.canvas = FigureCanvas(self.figure)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.ttc_frames = []
        self.timestamps = []
        self.bin_centers = []
        if from_saved and 'ttc360' in main_dict:
            if isinstance(main_dict['ttc360'], str):
                ttc_path = os.path.join(self.main_dict['pwd'], main_dict['ttc360'])
                if os.path.exists(ttc_path):
                    with open(ttc_path, 'r') as f:
                        saved_data = json.load(f)
                    self.load_from_saved(saved_data)
            else:
                self.load_from_saved(main_dict['ttc360'])
        else:
            self.prepare_data()
            

    def prepare_data(self):
        base_path = os.path.join(self.main_dict['pwd'], 'csv')
        if 'lidar' not in self.main_dict:
            return False

        lidar_file = os.path.join(self.main_dict['pwd'], self.main_dict['lidar'])
        with open(lidar_file, 'r') as f:
            lidar_data = json.load(f)
            lidar_data = {int(k): v for k, v in lidar_data.items()}
            lidar_keys = sorted(lidar_data.keys())

        velocity_bags = self.main_dict['topics'].get('ssc_velocity', [])
        position_bags = self.main_dict['topics'].get('pos', [])
        heading_bags = self.main_dict['topics'].get('heading', [])
        common = list(set(velocity_bags) & set(position_bags) & set(heading_bags))
        if not common:
            return False

        combined_ttc = []
        for bag in common:
            base_path = os.path.join(self.main_dict['pwd'], 'csv')
            fset = [os.path.join(base_path, bag + ext) for ext in [".ssc_velocity", ".pos", ".heading"]]
            if not all(os.path.exists(f) for f in fset):
                continue
            dfset = [pd.read_csv(f) for f in fset]
            ttc_result = self.calc_ttc(dfset[0], dfset[1], dfset[2], lidar_data, lidar_keys)
            combined_ttc.extend(ttc_result)

        # Sort combined TTC by timestamps
        self.ttc_frames = sorted(combined_ttc, key=lambda x: x[0])
        self.timestamps = [ts for ts, _ in self.ttc_frames]

        
        self.timestamps = [ts for ts, _ in self.ttc_frames]
        if self.ttc_frames:    ##
            first_ts = self.ttc_frames[0][0]
            self.update_plot_at_timestamp(first_ts)

        
        snapshot = {}
        for ts, frame in self.ttc_frames:
            snapshot[str(ts)] = {"ttc": {str(k): float(v) for k, v in frame["ttc"].items()},
                                 "rel_vel": {str(k): float(v) for k, v in frame["rel_vel"].items()}}
        
        ttc_filename = self.main_dict['bags'][0] + '.ttc360'
        ttc_path = os.path.join(self.main_dict['pwd'], ttc_filename)

        with open(ttc_path, 'w') as f:
            json.dump(snapshot, f, indent=2)

        self.main_dict['ttc360'] = ttc_filename
        

        # Setup plot
        self.ax.set_ylim(0, 25)
        self.ax.set_theta_zero_location("N")
        self.ax.set_theta_direction(1)
        self.line, = self.ax.plot([], [], color='orange', lw=2)
        return True

    def calc_ttc(self, velocity_df, position_df, heading_df, lidar_data, lidar_keys):
        velocity_df['time'] = velocity_df['time'].astype(np.int64)
        position_df['time'] = position_df['time'].astype(np.int64)
        heading_df['time'] = heading_df['time'].astype(np.int64)

        ego_df = pd.merge_asof(
            pd.merge_asof(velocity_df.sort_values('time'),
            position_df.sort_values('time'),
            on='time', direction='nearest', tolerance=np.int64(5e7)),
            heading_df.sort_values('time'),
            on='time', direction='nearest', tolerance=np.int64(5e7)).dropna(subset=['velocity', 'lat', 'lon', 'heading'])

        bin_edges = np.linspace(0, 2 * np.pi, 13)
        self.bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        frames = []
        

        def find_closest_lidar_timestamp(ts, keys, tolerance_ns=5e7):
            i = np.searchsorted(keys, ts)
            if i == 0:
                return keys[0] if abs(keys[0] - ts) <= tolerance_ns else None
            if i == len(keys):
                return keys[-1] if abs(keys[-1] - ts) <= tolerance_ns else None
            before, after = keys[i - 1], keys[i]
            return before if abs(before - ts) <= abs(after - ts) else after

        def match_objects(frame1, frame2, max_match_dist=1.5):
            matches = []
            for i, obj1 in enumerate(frame1):
                pos1 = np.array(obj1[:2])
                closest_j = -1
                closest_dist = float('inf')
                for j, obj2 in enumerate(frame2):
                    pos2 = np.array(obj2[:2])
                    dist = np.linalg.norm(pos2 - pos1)
                    if dist < closest_dist and dist <= max_match_dist:
                        closest_dist = dist
                        closest_j = j
                if closest_j != -1:
                    matches.append((i, closest_j))
            return matches

        for i in range(len(lidar_keys) - 1):
            t0, t1 = lidar_keys[i], lidar_keys[i + 1]
            dt = (t1 - t0) * 1e-9  # in seconds

            frame0 = lidar_data[t0]
            frame1 = lidar_data[t1]
            matches = match_objects(frame0, frame1)
            
            ego_candidates = ego_df.loc[ego_df['time'] <= t0]
            if ego_candidates.empty:
                continue  
            ego_row = ego_candidates.iloc[-1]            
            ego_speed = ego_row['velocity']
            ego_heading_rad = np.deg2rad(ego_row['heading'])  
            ego_velocity = ego_speed * np.array([np.cos(ego_heading_rad), np.sin(ego_heading_rad)])

            ttc_map = {a: np.inf for a in range(12)}
            rel_vel_map = {a: np.nan for a in range(12)}

            for idx0, idx1 in matches:
                obj0 = np.array(frame0[idx0][:2])
                obj1 = np.array(frame1[idx1][:2])
                distance0 = np.linalg.norm(obj0)
                distance1 = np.linalg.norm(obj1)
                if distance0 < 1.0:
                    continue  
                
                rel_velocity = (distance1 - distance0) / dt
                
                if abs(rel_velocity) < 0.2:
                    rel_velocity = 0.0
                    
                ttc = distance0 / abs(rel_velocity) if rel_velocity != 0 else np.inf
                
                angle = ((np.arctan2(obj0[1], obj0[0])) + 2 * np.pi) % (2 * np.pi)
                bin_idx = int(np.floor(angle / (2 * np.pi) * 12)) % 12
                
                if ttc < ttc_map[bin_idx]:
                    ttc_map[bin_idx] = ttc
                    rel_vel_map[bin_idx] = rel_velocity


            frames.append((t0, {'ttc': ttc_map, 'rel_vel': rel_vel_map}))

        return frames


    def update_plot_at_timestamp(self, current_ts):
        if not self.ttc_frames:
            return
        idx = np.searchsorted(self.timestamps, current_ts)
        if idx >= len(self.timestamps):
            idx = len(self.timestamps) - 1
        ts, frame_data = self.ttc_frames[idx]
        ttc_map = frame_data['ttc']
        rel_vel_map = frame_data['rel_vel']

        # self.ax.clear()
        self.figure.clf()
        self.ax = self.figure.add_subplot(111, polar=True)
        self.ax.set_ylim(0, 6)
        self.ax.set_yticks([0, 1, 2, 3, 4, 5, 6])
        self.ax.set_yticklabels(['0', '1', '2', '3', '4', '5' ,'6'])
        self.ax.set_theta_zero_location("N")
        self.ax.set_theta_direction(1)
        self.ax.set_title(f"TTC 360° | Time: {ts}")
        
        # bar_width = np.deg2rad(30) 
        bar_width = 2 * np.pi / 12

        # for angle, ttc in ttc_map.items():
        # for bin_idx, ttc in ttc_map.items():
        for bin_idx in range(len(self.bin_centers)):
            ttc = ttc_map.get(bin_idx, np.inf)
            rel_vel = rel_vel_map.get(bin_idx, np.nan)
            angle = self.bin_centers[bin_idx]

            if not np.isfinite(ttc) or ttc > 15:
                continue
            if rel_vel < -0.2:
                color = 'red'
            elif rel_vel > 0.2:
                color = 'green'
            else:
                color = 'gray'
            self.ax.bar(angle, ttc, width=bar_width, color=color, alpha=0.8, bottom=0.0, edgecolor='k', linewidth=0.3)

        self.canvas.draw_idle()
        
    def load_from_saved(self, saved_data):
        self.ttc_frames = []
        bin_edges = np.linspace(0, 2 * np.pi, 13)
        self.bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        for ts_str, frame_data in saved_data.items():
            ts = int(ts_str)
            ttc_map = {int(k): float(v) for k, v in frame_data['ttc'].items()}
            rel_vel_map = {int(k): float(v) for k, v in frame_data['rel_vel'].items()}
            self.ttc_frames.append((ts, {'ttc': ttc_map, 'rel_vel': rel_vel_map}))            
        self.timestamps = [ts for ts, _ in self.ttc_frames]



