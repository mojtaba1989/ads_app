import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Template
import base64
from io import BytesIO
import folium
import plotly.graph_objects as go
import numpy as np
import os
from geopy.distance import geodesic
import re

from PyQt5.QtWidgets import QApplication, QFileDialog


file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

def infer_road_type(speed_limit):
    if speed_limit <= 25:
        return "Residential/School Zone"
    elif speed_limit <= 35:
        return "Urban Street / Collector"
    elif speed_limit <= 45:
        return "Arterial / Minor Highway"
    elif speed_limit <= 55:
        return "Rural Highway / Major Arterial"
    elif speed_limit <= 65:
        return "Divided Highway / State Route"
    elif speed_limit <= 75:
        return "Interstate / Freeway"
    else:
        return "High-speed Interstate (e.g., Texas 85 mph zone)"
    
def extract_speed(text):
    match = re.search(r'\bspeed limit.*?(\d+)\s*mph', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def get_closest(key, dict):
        try:
            return key, dict[key]
        except:
            key_n = min(dict.keys(), key=lambda x: abs(int(x) - int(key)))
            return key_n, dict[key_n]
        
def closest_value_and_index(lst, target):
    return min(enumerate(lst), key=lambda x: abs(x[1] - target))

folium_icon_colors = [
    'red',
    'blue',         # default
    'green',
    'purple',
    'orange',
    'darkred',
    'lightred',
    'beige',
    'darkblue',
    'darkgreen',
    'cadetblue',
    'darkpurple',
    'white',
    'pink',
    'lightblue',
    'lightgreen',
    'gray',
    'black',
    'lightgray'
]

class report_Generator:
    def __init__(self, main_dict, gps_dict) -> None:
        pass
        self.main_dict = main_dict
        self.gps = gps_dict

    def create_map(self):
        route = [[lat, lon] for lat, lon in self.gps.values()]
        center = [np.mean([P[0] for P in route]),
                  np.mean([P[1] for P in route])]
        self.map = folium.Map(location=center, zoom_start=18)
        folium.PolyLine(route,
                        color="blue",
                        weight=8,
                        opacity=1,
                        smooth_factor=0).add_to(self.map)
        bound = [[np.min([P[0] for P in route]), np.min([P[1] for P in route])],
                 [np.max([P[0] for P in route]), np.max([P[1] for P in route])]]
        
        self.scen_list = [self.main_dict['scenarios'][key][1] for key in self.main_dict['scenarios']]
        self.scen_list = np.unique(self.scen_list)
        self.scen_dict = {}
        for id, sc in enumerate(self.scen_list):
            self.scen_dict[sc] = {'color': folium_icon_colors[id], 'locs': [],
                             'mrk_grp': folium.FeatureGroup(name=sc, show=True)}
        
        for key in self.main_dict['scenarios'].keys():
            loc = get_closest(int(key), self.gps)[1]
            self.scen_dict[self.main_dict['scenarios'][key][1]]['locs'].append(loc)
        
        for key in self.scen_dict.keys():
            for loc in self.scen_dict[key]['locs']:
                folium.Marker(loc,
                               popup=key, 
                               icon=folium.Icon(color=self.scen_dict[key]['color'])
                               ).add_to(self.scen_dict[key]['mrk_grp'])
            self.scen_dict[key]['mrk_grp'].add_to(self.map)
        folium.LayerControl(collapsed=False).add_to(self.map)
        self.map.fit_bounds(bound)
    
    def creat_driving_instruction_map(self):
        route = [[lat, lon] for lat, lon in self.gps.values()]
        center = [np.mean([P[0] for P in route]),
                  np.mean([P[1] for P in route])]
        self.map_DI = folium.Map(location=center, zoom_start=18)
        folium.PolyLine(route,
                        color="blue",
                        weight=8,
                        opacity=1,
                        smooth_factor=0).add_to(self.map_DI)
        bound = [[np.min([P[0] for P in route]), np.min([P[1] for P in route])],
                 [np.max([P[0] for P in route]), np.max([P[1] for P in route])]]
        
        self.di_list = [self.main_dict['HereAPI'][key]['type'] for key in self.main_dict['HereAPI']]
        self.di_list = np.unique(self.di_list)
        self.di_dict = {}
        for id, sc in enumerate(self.di_list):
            self.di_dict[sc] = {'color': folium_icon_colors[id], 'locs': [],
                             'mrk_grp': folium.FeatureGroup(name=sc, show=True)}
        
        for key in self.main_dict['HereAPI'].keys():

            self.di_dict[self.main_dict['HereAPI'][key]['type']]['locs'].append(self.main_dict['HereAPI'][key]['location'])
        
        for key in self.di_dict.keys():
            for loc in self.di_dict[key]['locs']:
                folium.Marker(loc,
                               popup=key, 
                               icon=folium.Icon(color=self.di_dict[key]['color'])
                               ).add_to(self.di_dict[key]['mrk_grp'])
            self.di_dict[key]['mrk_grp'].add_to(self.map_DI)
        folium.LayerControl(collapsed=False).add_to(self.map_DI)
        self.map_DI.fit_bounds(bound)


    def create_plots(self):
        self.plot_list = []
        if 'plots' not in self.main_dict.keys():
            return
        for plt in self.main_dict['plots']:
            time = []
            y = []
            for file in self.main_dict['topics'][plt[1]]:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + plt[1])
                data = pd.read_csv(file_path)
                if plt[2] in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        y.append(data[plt[2]][i])
                else:
                    continue
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=time, y=y, mode='lines+markers', name='y = x²'))
            fig.update_layout(xaxis_title='time (s)',
                            yaxis_title=plt[2])

            self.plot_list.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
            
    def create_html(self):
        with open(os.path.join(dir_path, 'report_template.html'), 'r') as f:
            self.html_template = f.read()

    def create_piechart(self):
        fig, ax = plt.subplots()
        sizes = [len(self.scen_dict[key]['locs']) for key in self.scen_dict.keys()]
        labels = [key for key in self.scen_dict.keys()]
        colors = [self.scen_dict[key]['color'] for key in self.scen_dict.keys()]
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.axis('equal') 

        # Save to base64 string
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()

        # HTML-safe image
        self.pie_data = f"data:image/png;base64,{encoded}"

    def create_DI_piechart(self):
        total_distance = 0
        ros_time = [key for key in self.gps.keys()]
        ros_time_int = [int(key) for key in self.gps.keys()]
        ros_time.sort()
        ros_time_int.sort()
        distance = []
        for i, key in enumerate(ros_time):
            if i == 0:
                distance.append(total_distance)
                continue
            Pfrom = tuple(self.gps[ros_time[i-1]])
            Pto = tuple(self.gps[ros_time[i]])
            total_distance += geodesic(Pfrom, Pto).mi
            distance.append(total_distance)
        
        slc_dist = [0]
        slc_value = []
        for key in self.main_dict['HereAPI'].keys():
            if self.main_dict['HereAPI'][key]['type']=='speed limit':
                idx, _ = closest_value_and_index(ros_time_int, int(key))
                slc_dist.append(distance[idx])
                slc_value.append(self.main_dict['HereAPI'][key]['value'])
        slc_dist.append(distance[-1])
        slc_dist = list(np.diff(slc_dist))
        slc_value.insert(0, slc_value[0])
        slc_init = []
        for i in range(len(slc_dist)):
            slc_init.append((slc_value[i], slc_dist[i]))
        
        tmp = np.unique(slc_value)
        slc_speed = []
        for val in tmp:
            total = 0
            for i in range(len(slc_init)):
                if val==slc_init[i][0]:
                    total =+ slc_init[i][1]
            slc_speed.append((val, total))

        tmp = np.unique([infer_road_type(i) for i in slc_value])
        slc_type = []
        for val in tmp:
            total = 0
            for i in range(len(slc_init)):
                if val==infer_road_type(slc_init[i][0]):
                    total =+ slc_init[i][1]
            slc_type.append((val, total))
            

        fig, axs = plt.subplots(1, 2, figsize=(10, 5))
        axs[0].pie([i[1] for i in slc_speed], labels=[f"{i[0]} mph" for i in slc_speed], autopct='%1.1f%%', startangle=90)
        axs[0].set_title("Speed Limit vs Travel distance")

        axs[1].pie([i[1] for i in slc_type], labels=[i[0] for i in slc_type], autopct='%1.1f%%', startangle=90)
        axs[1].set_title("Speed Limit vs Road type")
        for ax in axs:
            ax.axis('equal')
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        self.pie_DI_data = f"data:image/png;base64,{encoded}"

    def create_vehicle_dynamics(self):
        self.vehicle_dynamics = {}
        if "ssc_velocity" in self.main_dict['topics'].keys():
            time = []
            speed = []
            for file in self.main_dict['topics']['ssc_velocity']:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + 'ssc_velocity')
                data = pd.read_csv(file_path)
                if 'velocity' in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        speed.append(data['velocity'][i])
                else:
                    continue
            speed = np.array(speed)
            time = np.array(time)
            threshold = 0.3
            stopped = speed < threshold
            stop_segments = np.diff(stopped.astype(int)) == 1
            num_full_stops = np.sum(stop_segments)

            # self.vehicle_dynamics['Average Speed m/s'] = f"{np.mean(speed[speed>0]):.f}"
            # self.vehicle_dynamics['Average Speed kph'] = f"{np.mean(speed[speed>0])*3.6:.f}"
            self.vehicle_dynamics['Average Speed (mph)'] = f"{np.mean(speed[speed>0])*2.23694:.01f}"
            self.vehicle_dynamics['Maximum Speed (mph)'] = f"{np.max(speed)*2.23694:.01f}"
            self.vehicle_dynamics['Number of full stops'] = f"{num_full_stops}"
        else:
            self.vehicle_dynamics['Average Speed (mph)'] = f"not available"
            self.vehicle_dynamics['Maximum Speed (mph)'] = f"not available"
            self.vehicle_dynamics['Number of full stops'] = f"not available"

        if "ssc_velocity" in self.main_dict['topics'].keys():
            time = []
            accel = []
            for file in self.main_dict['topics']['ssc_velocity']:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + 'ssc_velocity')
                data = pd.read_csv(file_path)
                if 'acceleration' in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        accel.append(data['acceleration'][i])
                else:
                    continue

            accel = np.array(accel)
            time = np.array(time)
            self.vehicle_dynamics['Maximum Acceleration (m/s/s)'] = f"{np.max(accel):.01f}"
            self.vehicle_dynamics['Maximum Decceleration (m/s/s)'] = f"{np.min(accel):.01f}"
        else:
            self.vehicle_dynamics['Maximum Acceleration (m/s/s)'] = f"not available"
            self.vehicle_dynamics['Maximum Decceleration (m/s/s)'] = f"not available"

        if "vehi_steering_report" in self.main_dict['topics'].keys():
            time = []
            vs = []
            for file in self.main_dict['topics']['vehi_steering_report']:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + 'vehi_steering_report')
                data = pd.read_csv(file_path)
                if 'steering_wheel_angle' in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        vs.append(data['steering_wheel_angle'][i])
                else:
                    continue
            vs = np.array(vs)
            time = np.array(time)/1E9

            steering_rate = np.diff(vs) / np.diff(time)
            self.vehicle_dynamics['Maximum Steering Rate (rad/s)'] = f"{np.max(np.abs(steering_rate)):.01f}"
        else:
            self.vehicle_dynamics['Maximum Steering Rate (rad/s)'] = f"not available"
       
    def generate_report(self):
        self.create_html()
        self.create_map()
        self.creat_driving_instruction_map()
        self.create_plots()
        self.create_piechart()
        self.create_DI_piechart()
        self.create_vehicle_dynamics()

        html_content = Template(self.html_template).render(
            map_html=self.map._repr_html_(),
            map_DI_html=self.map_DI._repr_html_(),
            plots = self.plot_list,
            info = self.main_dict['info'],
            pie_data = self.pie_data,
            pie_DI_data = self.pie_DI_data,
            vehicle_dynamics = self.vehicle_dynamics
        )

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Report",
            "report.html",  # default file name
            "HTML Files (*.html);;All Files (*)"
        )

        if file_path:
            print("File will be saved to:", file_path)
            with open(file_path, 'w') as f:
                f.write(html_content)
        else:
            pass
