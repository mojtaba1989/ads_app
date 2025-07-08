#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import csv
import re
import math
import utm
import folium
import requests
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime

class HereMapRouteAnalyzer:
    def __init__(self):
        self.csv_dir = "csv"
        self.route_name = None
        self.gps_points = []
        self.total_distance_m = 0
        self.heremap_route = None
        self.heremap_distance_m = 0
        self.route_dataframe = None
        self.heremap_api_responses = []
        
        self.api_key = 'uUFZJMYlitfRsDjEJIHqZ1fWoc6jhycasfFwsIBlhWs'
        self.routing_url = "https://router.hereapi.com/v8/routes"
    
    def load_data(self):
        pos_files = glob.glob(os.path.join(self.csv_dir, "*.pos"))
                
        rosbagcsv_files = []
        for pos_file in pos_files:
            basename = os.path.basename(pos_file).replace('.bag.pos', '')
            pattern = r'(\d{4}-\d{2}-\d{2})-(\d{2}-\d{2}-\d{2})_(\d+)'
            match = re.match(pattern, basename)
            
            if match:
                file_info = {
                    'filename': pos_file,
                    'basename': basename,
                    'date': match.group(1),
                    'sequence': int(match.group(3))
                }
            else:
                file_info = {
                    'filename': pos_file,
                    'basename': basename,
                    'sequence': 0
                }
            rosbagcsv_files.append(file_info)
        
        rosbagcsv_files.sort(key=lambda x: x['sequence'])
        
        if rosbagcsv_files:
            first, last = rosbagcsv_files[0], rosbagcsv_files[-1]
            self.route_name = f"{first['date']}_seq{first['sequence']}-{last['sequence']}"
        
        print(f"Found {len(rosbagcsv_files)} files: {self.route_name}")
        
        self.gps_points = []
        
        for rosbag_data in rosbagcsv_files:
            file_gps_data = []
            try:
                with open(rosbag_data['filename'], 'r') as f:
                    reader = csv.DictReader(f)
                    index = 0
                    
                    for row in reader:
                        try:
                            lat, lon = float(row['lat']), float(row['lon'])
                            if -90 <= lat <= 90 and -180 <= lon <= 180:
                                file_gps_data.append({
                                    'lat': lat,
                                    'lon': lon,
                                    'hgt': float(row['hgt']),
                                    'ros_time': float(row['time']),
                                    'source_rosbag': rosbag_data['basename'],
                                    'sequence': rosbag_data['sequence'],
                                    'index_in_sequence': index
                                })
                                index += 1
                        except (ValueError, KeyError):
                            continue
            except Exception:
                continue
            #sortagaibn to validate
            file_gps_data.sort(key=lambda x: x['ros_time'])
            self.gps_points.extend(file_gps_data)
        
        self.gps_points.sort(key=lambda x: (x['sequence'], x['ros_time']))
        print(f"Loaded {len(self.gps_points)} GPS points")
        return self.gps_points
    
    def calculate_utm_distance(self):
        if len(self.gps_points) < 2:
            return 0
        
        total_distance = 0
        starting_utm_x, starting_utm_y = None, None
        
        for point in self.gps_points:
            utm_x, utm_y, zone_num, zone_letter = utm.from_latlon(point['lat'], point['lon'])
            point.update({'utm_x': utm_x, 'utm_y': utm_y})
            
            if starting_utm_x is not None:
                dx, dy = utm_x - starting_utm_x, utm_y - starting_utm_y
                distance = math.sqrt(dx*dx + dy*dy)
                total_distance += distance
                point['cumulative_distance'] = total_distance
            else:
                point['cumulative_distance'] = 0
            
            starting_utm_x, starting_utm_y = utm_x, utm_y
        
        self.total_distance_m = total_distance
        print(f"Route distance: {total_distance/1000:.2f} km")
        return total_distance
    
    def request_heremap_route(self):
        #only if more than 2 gps points in csv is present thhen start
        if len(self.gps_points) < 2:
            return None
        
        segments = self.create_route_segments(num_segments=20)
        if not segments:
            return None
        
        print(f"Processing {len(segments)} segments...")
        
        all_coordinates = []
        all_speed_limits = []
        total_heremap_distance = 0
        successful_segments = 0
        
        for i, segment in enumerate(segments):
            start_point = segment['start_point']
            end_point = segment['end_point']
            
            params = {
                'apikey': self.api_key,
                'transportMode': 'car',
                'origin': f"{start_point['lat']:.6f},{start_point['lon']:.6f}",
                'destination': f"{end_point['lat']:.6f},{end_point['lon']:.6f}",
                'return': 'polyline,summary,actions,instructions',
                'spans': 'speedLimit,dynamicSpeedInfo'
            }
            
            try:
                response = requests.get(self.routing_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    route_data = response.json()
                    
                    segment_response = {
                        'segment_id': i,
                        'request_params': params,
                        'response_data': route_data,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.heremap_api_responses.append(segment_response)
                    
                    if 'routes' in route_data and route_data['routes']:
                        route = route_data['routes'][0]
                        
                        distance_m = 0
                        if 'summary' in route:
                            distance_m = route['summary'].get('length', 0)
                        
                        if distance_m == 0 and 'sections' in route:
                            for section in route['sections']:
                                if 'summary' in section:
                                    distance_m += section['summary'].get('length', 0)
                        
                        if distance_m == 0 and 'sections' in route:
                            for section in route['sections']:
                                if 'spans' in section:
                                    for span in section['spans']:
                                        distance_m += span.get('length', 0)
                        
                        segment_coords = []
                        step = max(1, len(segment['points']) // 5)
                        for j in range(0, len(segment['points']), step):
                            point = segment['points'][j]
                            segment_coords.append([point['lat'], point['lon']])
                        
                        segment_speed_limits = []
                        if 'sections' in route:
                            for section in route['sections']:
                                if 'spans' in section:
                                    for span in section['spans']:
                                        if 'speedLimit' in span:
                                            speed_limit = span['speedLimit']
                                            if isinstance(speed_limit, dict) and 'maxSpeed' in speed_limit:
                                                segment_speed_limits.append(speed_limit['maxSpeed'])
                                            elif isinstance(speed_limit, (int, float)):
                                                segment_speed_limits.append(speed_limit)
                        
                        all_coordinates.extend(segment_coords)
                        all_speed_limits.extend(segment_speed_limits)
                        total_heremap_distance += distance_m
                        successful_segments += 1
                        
            except Exception:
                pass
            
            time.sleep(0.1)
        
        if all_coordinates:
            self.heremap_route = {
                'polyline': None,
                'coordinates': all_coordinates,
                'distance_m': total_heremap_distance,
                'duration_s': 0,
                'speed_limits': all_speed_limits
            }
            self.heremap_distance_m = total_heremap_distance
            
            print(f"HERE Maps: {successful_segments}/{len(segments)} segments, {total_heremap_distance/1000:.2f} km")
            return self.heremap_route
        else:
            return None
    
    def create_route_segments(self, num_segments=20):
        #CREATED ONLY 20 SEGMENTS, CAN CREATE MORE OR LESS ACCORDING TO THE ROUTE AND DISTANCE
        if len(self.gps_points) < 2:
            return []
        
        total_distance = self.total_distance_m
        segment_distance = total_distance / num_segments
        segments = []
        
        current_start_idx = 0
        segment_id = 1
        
        for target_segment in range(1, num_segments + 1):
            target_distance = target_segment * segment_distance
            
            segment_end_idx = current_start_idx + 1
            while (segment_end_idx < len(self.gps_points) and 
                   self.gps_points[segment_end_idx]['cumulative_distance'] < target_distance):
                segment_end_idx += 1
            
            segment_end_idx = min(segment_end_idx, len(self.gps_points) - 1)
            
            if target_segment == num_segments:
                segment_end_idx = len(self.gps_points) - 1
            
            if segment_end_idx > current_start_idx:
                segment_points = self.gps_points[current_start_idx:segment_end_idx + 1]
                
                start_distance = self.gps_points[current_start_idx]['cumulative_distance']
                end_distance = self.gps_points[segment_end_idx]['cumulative_distance']
                
                segment = {
                    'segment_id': segment_id,
                    'start_point': segment_points[0],
                    'end_point': segment_points[-1],
                    'points': segment_points,
                    'point_count': len(segment_points),
                    'distance_m': end_distance - start_distance,
                    'start_distance_m': start_distance,
                    'end_distance_m': end_distance
                }
                segments.append(segment)
                segment_id += 1
                current_start_idx = segment_end_idx
        
        return segments
    
    def match_heremap_to_gps(self, here_coordinates):
        if not here_coordinates or not self.gps_points:
            return [None] * len(self.gps_points), [None] * len(self.gps_points)
        
        here_lat_matched = []
        here_lon_matched = []
        here_coords_array = np.array(here_coordinates)
        
        for gps_point in self.gps_points:
            gps_lat, gps_lon = gps_point['lat'], gps_point['lon']
            
            distances = np.sqrt(
                (here_coords_array[:, 0] - gps_lat) ** 2 + 
                (here_coords_array[:, 1] - gps_lon) ** 2
            )
            
            closest_idx = np.argmin(distances)
            closest_here_coord = here_coords_array[closest_idx]
            
            here_lat_matched.append(closest_here_coord[0])
            here_lon_matched.append(closest_here_coord[1])
        
        return here_lat_matched, here_lon_matched
    
    def create_route_dataframe(self):
        if not self.gps_points:
            return None
        
        gps_data = []
        for point in self.gps_points:
            gps_data.append({
                'time': point['ros_time'],
                'lat': point['lat'],
                'lon': point['lon'],
                'hgt': point['hgt'],
                'sequence': point['sequence'],
                'source_rosbag': point['source_rosbag'],
                'index_in_sequence': point.get('index_in_sequence', 0),
                'utm_x': point.get('utm_x', None),
                'utm_y': point.get('utm_y', None),
                'cumulative_distance': point.get('cumulative_distance', 0)
            })
        
        df = pd.DataFrame(gps_data)
        
        if self.heremap_route and self.heremap_route['coordinates']:
            here_coords = self.heremap_route['coordinates']
            here_lat, here_lon = self.match_heremap_to_gps(here_coords)
            
            df['here_lat'] = here_lat
            df['here_lon'] = here_lon
            
            df['gps_heremap_distance_m'] = np.sqrt(
                (df['lat'] - df['here_lat']) ** 2 + 
                (df['lon'] - df['here_lon']) ** 2
            ) * 111000
        else:
            df['here_lat'] = None
            df['here_lon'] = None
            df['gps_heremap_distance_m'] = None
        
        if self.heremap_route and self.heremap_route['speed_limits']:
            speed_limits = self.heremap_route['speed_limits']
            df['here_speed_limit_ms'] = [speed_limits[i % len(speed_limits)] for i in range(len(df))]
            df['here_speed_limit_kmh'] = df['here_speed_limit_ms'] * 3.6
        else:
            df['here_speed_limit_ms'] = None
            df['here_speed_limit_kmh'] = None
        
        #df['index'] = range(len(df))
        #df['time_diff'] = df['time'].diff().fillna(0)
        #df['sequence_transition'] = df['sequence'].diff() != 0
        
        self.route_dataframe = df
        return df
    
    def export_to_csv(self, filename=None):
        if self.route_dataframe is None:
            return None
        
        if filename is None:
            filename = f"{self.route_name}_route_analysis.csv"
        
        self.route_dataframe.to_csv(filename, index=False)
        print(f"Exported: {filename}")
        return filename
    
    def export_heremap_json(self, filename=None):
        if not self.heremap_api_responses:
            return None
        
        if filename is None:
            filename = f"{self.route_name}_heremap_api_responses.json"
        
        json_data = {
            'route_name': self.route_name,
            'export_timestamp': datetime.now().isoformat(),
            'total_segments': len(self.heremap_api_responses),
            'api_responses': self.heremap_api_responses
        }
        
        with open(filename, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        print(f"Exported: {filename}")
        return filename
    
    def create_map(self):
        if not self.gps_points:
            return None
        
        lats = [p['lat'] for p in self.gps_points]
        lons = [p['lon'] for p in self.gps_points]
        center = [sum(lats)/len(lats), sum(lons)/len(lons)]
        
        m = folium.Map(location=center, zoom_start=15)
        
        gps_coords = [[p['lat'], p['lon']] for p in self.gps_points]
        folium.PolyLine(
            gps_coords, 
            weight=4, 
            color='blue', 
            opacity=0.8,
            popup=f"GPS: {self.total_distance_m/1000:.2f} km"
        ).add_to(m)
        
        if self.heremap_route and self.heremap_route['coordinates']:
            folium.PolyLine(
                self.heremap_route['coordinates'],
                weight=4,
                color='red',
                opacity=0.7,
                popup=f"HERE Maps: {self.heremap_distance_m/1000:.2f} km"
            ).add_to(m)
        
        start, end = self.gps_points[0], self.gps_points[-1]
        folium.Marker([start['lat'], start['lon']], 
                     icon=folium.Icon(color='green', icon='play')).add_to(m)
        folium.Marker([end['lat'], end['lon']], 
                     icon=folium.Icon(color='red', icon='stop')).add_to(m)
        
        map_file = f"{self.route_name}_map.html"
        m.save(map_file)
        print(f"Map: {map_file}")
        return map_file
    
    def get_summary(self):
        sequences = {}
        for point in self.gps_points:
            seq = point['sequence']
            if seq not in sequences:
                sequences[seq] = {'count': 0}
            sequences[seq]['count'] += 1
        
        return {
            'route_name': self.route_name,
            'total_sequences': len(sequences),
            'total_gps_points': len(self.gps_points),
            'gps_distance_km': self.total_distance_m / 1000,
            'heremap_distance_km': self.heremap_distance_m / 1000,
            'speed_limits': list(set(self.heremap_route['speed_limits'])) if self.heremap_route else [],
            'dataframe_shape': self.route_dataframe.shape if self.route_dataframe is not None else None
        }

def main():
    HRouter = HereMapRouteAnalyzer()
    
    HRouter.load_data()
    HRouter.calculate_utm_distance()
    HRouter.request_heremap_route()
    HRouter.create_route_dataframe()
    HRouter.create_map()
    
    csv_file = HRouter.export_to_csv()
    json_file = HRouter.export_heremap_json()
    
    summary = HRouter.get_summary()
    print(f"Route: {summary['route_name']}")
    print(f"GPS Points: {summary['total_gps_points']}")
    print(f"GPS Distance: {summary['gps_distance_km']:.2f} km")
    print(f"HERE Maps Distance: {summary['heremap_distance_km']:.2f} km")
    print(f"Speed Limits: {summary['speed_limits']}")
    print(f"Dataframe: {summary['dataframe_shape']}")
    
    return HRouter

if __name__ == "__main__":
    HRouter = main()
