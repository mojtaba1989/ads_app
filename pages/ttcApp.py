import os
import pandas as pd
import numpy as np
import json

def find_closest_lidar_timestamp(ts, keys, tolerance_ns=5e7):
    i = np.searchsorted(keys, ts)
    if i == 0:
        return keys[0] if abs(keys[0] - ts) <= tolerance_ns else None
    if i == len(keys):
        return keys[-1] if abs(keys[-1] - ts) <= tolerance_ns else None
    before, after = keys[i - 1], keys[i]
    return before if abs(before - ts) <= abs(after - ts) else after


class TTCPlotApp():
    def __init__(self, main_dict):
        self.main_dict = main_dict


    def run(self):
        base_path = os.path.join(self.main_dict['pwd'], 'csv')
        if not 'lidar' in self.main_dict.keys():
            return False
        
        lidar_file = os.path.join(self.main_dict['pwd'], self.main_dict['lidar'])
        with open(lidar_file, 'r') as f:
            lidar_data = json.load(f)
            lidar_data = {int(k): v for k, v in lidar_data.items()}
            lidar_keys = sorted(lidar_data.keys())
        
        velocity_bags = [i for i in self.main_dict['topics']['ssc_velocity']]
        position_bags = [i for i in self.main_dict['topics']['pos']]
        heading_bags = [i for i in self.main_dict['topics']['heading']]

        common = list(set(velocity_bags) & set(position_bags) & set(heading_bags))
        if not common:
            return False
        
        self.main_dict['topics'].pop('time_to_collision', None) #remove before add
        
        for bag in common:
            fset = [os.path.join(base_path, bag + ext) for ext in [".ssc_velocity", ".pos", ".heading"]]
            dfset = [pd.read_csv(f) for f in fset] 
            ttc_df = self.calc_ttc(dfset[0], dfset[1], dfset[2], lidar_data, lidar_keys)
            if not ttc_df is None:
                ttc_file_path = os.path.join(base_path, bag + '.time_to_collision')
                ttc_df.to_csv(ttc_file_path, index=None)
                if 'time_to_collision' in self.main_dict['topics'].keys():
                    self.main_dict['topics']['time_to_collision'].append(bag)
                else:
                    self.main_dict['topics']['time_to_collision'] = [bag]
        return 'time_to_collision' in self.main_dict['topics'].keys()


    def calc_ttc(self, velocity_df, position_df, heading_df, lidar_data, lidar_keys):
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
            return None
                        
        ttc_records.sort()
        time = [rec[0] for rec in ttc_records]
        ttc = [rec[1] for rec in ttc_records]
        
        df = pd.DataFrame({'time':time,
                           'ttc':ttc})
        return df

