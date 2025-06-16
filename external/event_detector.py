
import pandas as pd

class EventDetector:
    def __init__(self, ssc_velocity, steering_feedback, cam_zed2i):
        # assert isinstance(ssc_velocity, pd.DataFrame), "ssc_velocity must be a DataFrame"
        # assert isinstance(steering_feedback, pd.DataFrame), "steering_feedback must be a DataFrame"
        # assert isinstance(cam_zed2i, pd.DataFrame), "cam_zed2i must be a DataFrame"

        self.velocity = ssc_velocity.sort_values('time')
        self.steering = steering_feedback.sort_values('time')
        self.cam = cam_zed2i.sort_values('time')

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
        self.velocity['accel_diff'] = self.velocity['acceleration'].diff()


        # Lane Changes and Turns (merge steering and velocity)
        merged = pd.merge_asof(
            self.steering[['time', 'steering']].sort_values('time'),
            self.velocity[['time', 'velocity']].sort_values('time'),
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

        # Sync with cam_zed2i timestamps
        if not self.cam.empty:
            cam_start = self.cam['time'].min()
            cam_end = self.cam['time'].max()
            events = events[(events['time'] >= cam_start) & (events['time'] <= cam_end)]

            events = pd.merge_asof(
                events.sort_values('time'),
                self.cam[['time', 'seq']].sort_values('time'),
                on='time',
                direction='nearest',
                tolerance=100_000_000)

        return events[['time', 'event', 'seq']].dropna()



    # def detect_events(self):
    #     # Merge steering and velocity
    #     df = pd.merge_asof(
    #         self.steering[['time', 'steering']],
    #         self.velocity[['time', 'velocity']],on='time').dropna()

    #     if df.empty or 'steering' not in df.columns or 'velocity' not in df.columns:
    #         return pd.DataFrame(columns=['time', 'event', 'seq'])

    #     # Lane Change: steering > 0.8
    #     lane_change = df[df['steering'] > 0.8].copy()
    #     lane_change = self.filter_rapid_events(lane_change, min_gap_secs=6)
    #     lane_change['event'] = 'Lane Change'

    #     # Turn: velocity < 8 AND steering > 2.0
    #     turn = df[(df['velocity'] < 8) & (df['steering'] > 2.0)].copy()
    #     turn = self.filter_rapid_events(turn, min_gap_secs=10)
    #     turn['event'] = 'Turn'

    #     # Combine and merge with cam_zed2i for seq
    #     df_events = pd.concat([lane_change, turn])
    #     df_events = pd.merge_asof(
    #         df_events.sort_values('time'),
    #         self.cam[['time', 'seq']].sort_values('time'),
    #         on='time',direction='nearest',tolerance=100_000_000)

    #     return df_events[['time', 'event', 'seq']].dropna()
